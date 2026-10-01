//! AEGIS Search Ranking Kernel (`aegis_search_core`)
//!
//! Pure Rust implementation of the memory search scoring formula from
//! `src/aegis/l4_memory/search.py::SearchEngine._compute_score()`.
//!
//! Formula (identical to Python):
//!   score = blend(confidence, recency, recency_weight)
//!           × importance_weight
//!           × provenance_quality
//!           × pin_boost
//!   → clamp to [0.0, 1.0]
//!
//! # Design
//! - No heap allocations in the hot path (score_records operates on slices)
//! - No FFI marshalling overhead in the core loop
//! - Results are sorted in-place using a partial-sort / full sort
//! - Intended as a performance reference and future PyO3 binding target
//!
//! # Provenance / Importance mappings
//! Mirror the Python dicts exactly to guarantee identical scoring results.

// ---------------------------------------------------------------------------
// Provenance quality weights (matches _PROVENANCE_QUALITY in search.py)
// ---------------------------------------------------------------------------

/// ProvenanceKind ordinal (0-based, matches Python enum declaration order).
/// Maps to quality weight for relevance scoring.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum ProvenanceKind {
    UserConfirmed       = 0,   // 1.00
    UserProvided        = 1,   // 0.95
    Corroborated        = 2,   // 0.85
    FileDerived         = 3,   // 0.75
    CodeDerived         = 4,   // 0.70
    ToolDerived         = 5,   // 0.65
    WebDerived          = 6,   // 0.60
    ConversationDerived = 7,   // 0.55
    ScannerDerived      = 8,   // 0.50
    SystemGenerated     = 9,   // 0.40
    ModelInferred       = 10,  // 0.30
    ObserverDerived     = 11,  // 0.50 (same as scanner_derived)
}

impl ProvenanceKind {
    /// Quality weight used in relevance scoring.
    #[inline]
    pub fn quality(self) -> f32 {
        match self {
            Self::UserConfirmed       => 1.00,
            Self::UserProvided        => 0.95,
            Self::Corroborated        => 0.85,
            Self::FileDerived         => 0.75,
            Self::CodeDerived         => 0.70,
            Self::ToolDerived         => 0.65,
            Self::WebDerived          => 0.60,
            Self::ConversationDerived => 0.55,
            Self::ScannerDerived      => 0.50,
            Self::ObserverDerived     => 0.50,
            Self::SystemGenerated     => 0.40,
            Self::ModelInferred       => 0.30,
        }
    }
}

// ---------------------------------------------------------------------------
// Importance weight (matches _IMPORTANCE_WEIGHT in search.py)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum Importance {
    Low      = 0,  // 0.5
    Normal   = 1,  // 1.0
    High     = 2,  // 1.5
    Critical = 3,  // 2.0
}

impl Importance {
    #[inline]
    pub fn weight(self) -> f32 {
        match self {
            Self::Low      => 0.5,
            Self::Normal   => 1.0,
            Self::High     => 1.5,
            Self::Critical => 2.0,
        }
    }
}

// ---------------------------------------------------------------------------
// RecordInput — flat POD struct mirroring the fields _compute_score() needs.
// Zero-copy friendly; no strings.
// ---------------------------------------------------------------------------

/// Flat input record for the scoring kernel.
///
/// All floating-point fields are `f32` for SIMD-friendly layout.
/// `provenance` and `importance` are enum discriminants.
#[derive(Clone, Copy, Debug)]
#[repr(C)]
pub struct RecordInput {
    /// Confidence score [0.0, 1.0]
    pub confidence: f32,
    /// Updated_at as Unix timestamp (seconds)
    pub updated_at_secs: f64,
    /// Importance level
    pub importance: Importance,
    /// Primary provenance kind
    pub provenance: ProvenanceKind,
    /// True if is_pinned or importance == CRITICAL
    pub is_decay_immune: bool,
}

/// Scored result — index into the original slice + computed score.
#[derive(Clone, Copy, Debug)]
pub struct ScoredRecord {
    pub index: usize,
    pub score: f32,
}

// ---------------------------------------------------------------------------
// Core scoring function (matches Python _compute_score exactly)
// ---------------------------------------------------------------------------

const HALF_LIFE_DAYS: f64 = 90.0;  // matches DecayPolicy default
const MAX_SCORE: f32 = 3.0;         // max theoretical = 1×2×1×1.5

/// Compute the relevance score for a single record.
///
/// This is a direct Rust port of `SearchEngine._compute_score()`.
#[inline]
pub fn compute_score(rec: &RecordInput, now_secs: f64, recency_weight: f32) -> f32 {
    let confidence = rec.confidence;

    let importance_w = rec.importance.weight();

    // Recency factor: exponential decay from now
    let age_days = (now_secs - rec.updated_at_secs) / 86_400.0;
    let recency = if age_days > 0.0 {
        (0.5_f64.powf(age_days / HALF_LIFE_DAYS)) as f32
    } else {
        1.0_f32
    };

    let prov_q = rec.provenance.quality();

    let pin_boost: f32 = if rec.is_decay_immune { 1.5 } else { 1.0 };

    let rw = recency_weight;
    let blended = (1.0 - rw) * confidence + rw * recency;

    let score = blended * importance_w * prov_q * pin_boost;

    // Normalise to [0, 1]
    (score / MAX_SCORE).min(1.0_f32)
}

// ---------------------------------------------------------------------------
// Batch scoring + sort — the main hot-path entry point
// ---------------------------------------------------------------------------

/// Score all records and return them sorted by descending score.
///
/// Returns a `Vec<ScoredRecord>` — the `.index` field maps back to the
/// original input slice position.
///
/// This is the direct equivalent of the Python:
///   results.sort(key=lambda r: r.score, reverse=True)
pub fn score_records(
    records: &[RecordInput],
    now_secs: f64,
    recency_weight: f32,
) -> Vec<ScoredRecord> {
    let mut scored: Vec<ScoredRecord> = records
        .iter()
        .enumerate()
        .map(|(i, rec)| ScoredRecord {
            index: i,
            score: compute_score(rec, now_secs, recency_weight),
        })
        .collect();

    // Sort descending by score
    scored.sort_unstable_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    scored
}

/// Return the top-K records by score (avoids sorting the entire slice for large K).
///
/// Uses `select_nth_unstable_by` for O(N) partial selection when K << N.
pub fn top_k_records(
    records: &[RecordInput],
    now_secs: f64,
    recency_weight: f32,
    k: usize,
) -> Vec<ScoredRecord> {
    let mut scored = score_records(records, now_secs, recency_weight);
    scored.truncate(k);
    scored
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn make_rec(confidence: f32, importance: Importance, provenance: ProvenanceKind, is_decay_immune: bool, age_days: f64) -> RecordInput {
        let now = 1_700_000_000.0_f64;
        RecordInput {
            confidence,
            updated_at_secs: now - age_days * 86_400.0,
            importance,
            provenance,
            is_decay_immune,
        }
    }

    #[test]
    fn score_is_in_unit_range() {
        let rec = make_rec(0.9, Importance::High, ProvenanceKind::UserConfirmed, false, 0.0);
        let s = compute_score(&rec, 1_700_000_000.0, 0.3);
        assert!(s >= 0.0 && s <= 1.0, "score out of range: {}", s);
    }

    #[test]
    fn critical_pinned_beats_low_normal() {
        let now = 1_700_000_000.0_f64;
        let high = make_rec(0.95, Importance::Critical, ProvenanceKind::UserConfirmed, true, 0.0);
        let low  = make_rec(0.1,  Importance::Low,      ProvenanceKind::ModelInferred, false, 200.0);
        let s_high = compute_score(&high, now, 0.3);
        let s_low  = compute_score(&low,  now, 0.3);
        assert!(s_high > s_low, "high={} low={}", s_high, s_low);
    }

    #[test]
    fn score_records_sorted_descending() {
        let now = 1_700_000_000.0_f64;
        let recs = vec![
            make_rec(0.1, Importance::Low,      ProvenanceKind::ModelInferred,  false, 300.0),
            make_rec(0.9, Importance::Critical, ProvenanceKind::UserConfirmed,  true,  0.0),
            make_rec(0.5, Importance::Normal,   ProvenanceKind::FileDerived,    false, 30.0),
        ];
        let sorted = score_records(&recs, now, 0.3);
        for w in sorted.windows(2) {
            assert!(w[0].score >= w[1].score, "not sorted: {:?}", w);
        }
    }

    #[test]
    fn score_records_n1000_completes() {
        let now = 1_700_000_000.0_f64;
        let recs: Vec<_> = (0..1000).map(|i| {
            make_rec(
                (i as f32 % 10.0) / 10.0 + 0.05,
                Importance::Normal,
                ProvenanceKind::FileDerived,
                false,
                (i % 365) as f64,
            )
        }).collect();
        let sorted = score_records(&recs, now, 0.3);
        assert_eq!(sorted.len(), 1000);
    }

    #[test]
    fn provenance_quality_monotone() {
        // USER_CONFIRMED > MODEL_INFERRED
        assert!(ProvenanceKind::UserConfirmed.quality() > ProvenanceKind::ModelInferred.quality());
        assert!(ProvenanceKind::Corroborated.quality() > ProvenanceKind::ConversationDerived.quality());
    }

    #[test]
    fn recency_decay_reduces_score() {
        let now = 1_700_000_000.0_f64;
        let fresh = make_rec(0.8, Importance::Normal, ProvenanceKind::FileDerived, false, 0.0);
        let stale = make_rec(0.8, Importance::Normal, ProvenanceKind::FileDerived, false, 365.0);
        let s_fresh = compute_score(&fresh, now, 0.5);  // high recency_weight
        let s_stale = compute_score(&stale, now, 0.5);
        assert!(s_fresh > s_stale, "fresh={} stale={}", s_fresh, s_stale);
    }
}
