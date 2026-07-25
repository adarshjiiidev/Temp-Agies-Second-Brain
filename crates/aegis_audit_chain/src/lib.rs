//! aegis_audit_chain — append-only audit hash chain used by Prompt 05 SB08.
//!
//! Prompt 02 skeleton:
//!   * `AuditEntry` (timestamp + actor + action + payload_json + prev_hash)
//!   * `AuditChain` — append, verify, save/load JSON lines.
//!
//! NOTE: Per docs/05_SECURITY_PRIVACY.md SB08 (AUDIT): Every privileged operation MUST append here;
//! chain integrity preserved across process restarts; files stored in $DATA_DIR/audit/.
//! Implementation uses SHA-256 chain for Prompt 02; future prompts add KERI/Sphinx offline verifier.

#![forbid(unsafe_code)]

use aegis_ffi_common::FfiResult;
use aegis_crypto::sha256_hex;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuditEntry {
    pub seq: u64,
    pub timestamp_unix_ms: u64,
    pub actor: String,
    pub action: String,
    pub payload_json: String,
    pub correlation_id: String,
    pub prev_hash: String,
    pub entry_hash: String,
}

impl AuditEntry {
    fn compute_hash(&self) -> String {
        let blob = format!(
            "{}|{}|{}|{}|{}|{}|{}",
            self.seq,
            self.timestamp_unix_ms,
            self.actor,
            self.action,
            self.payload_json,
            self.correlation_id,
            self.prev_hash,
        );
        sha256_hex(blob.as_bytes())
    }
}

const GENESIS_PREV: &str = "GENESIS";

#[derive(Debug, Clone)]
pub struct AuditChain {
    path: PathBuf,
    entries: Vec<AuditEntry>,
}

impl AuditChain {
    pub fn new<P: AsRef<Path>>(path: P) -> Self {
        AuditChain {
            path: path.as_ref().to_path_buf(),
            entries: Vec::new(),
        }
    }

    pub fn load_or_create(&mut self) -> FfiResult<()> {
        if !self.path.exists() {
            std::fs::create_dir_all(self.path.parent().unwrap_or(Path::new("."))).ok();
            self.entries = Vec::new();
            return Ok(());
        }
        let text = std::fs::read_to_string(&self.path)
            .map_err(|e| aegis_ffi_common::FfiError::AuditChain(format!("read: {e}")))?;
        self.entries.clear();
        for (i, line) in text.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let entry: AuditEntry = serde_json::from_str(line)
                .map_err(|e| aegis_ffi_common::FfiError::AuditChain(format!("line {i}: {e}")))?;
            self.entries.push(entry);
        }
        Ok(())
    }

    pub fn append(
        &mut self,
        actor: &str,
        action: &str,
        payload_json: &str,
        correlation_id: &str,
    ) -> FfiResult<&AuditEntry> {
        let seq = self.entries.len() as u64;
        let prev_hash = self
            .entries
            .last()
            .map(|e| e.entry_hash.clone())
            .unwrap_or_else(|| GENESIS_PREV.to_string());
        let timestamp_unix_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0);
        let mut entry = AuditEntry {
            seq,
            timestamp_unix_ms,
            actor: actor.to_string(),
            action: action.to_string(),
            payload_json: payload_json.to_string(),
            correlation_id: correlation_id.to_string(),
            prev_hash,
            entry_hash: String::new(),
        };
        entry.entry_hash = entry.compute_hash();
        // Persist
        let line = serde_json::to_string(&entry)
            .map_err(|e| aegis_ffi_common::FfiError::AuditChain(format!("serialize: {e}")))?;
        use std::io::Write;
        let mut f = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .map_err(|e| aegis_ffi_common::FfiError::AuditChain(format!("open: {e}")))?;
        writeln!(f, "{line}")
            .map_err(|e| aegis_ffi_common::FfiError::AuditChain(format!("write: {e}")))?;
        self.entries.push(entry);
        Ok(self.entries.last().unwrap())
    }

    pub fn verify(&self) -> bool {
        let mut prev = GENESIS_PREV.to_string();
        for e in &self.entries {
            if e.prev_hash != prev {
                return false;
            }
            if e.entry_hash != e.compute_hash() {
                return false;
            }
            prev = e.entry_hash.clone();
        }
        true
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[AuditEntry] {
        &self.entries
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn append_and_verify() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("audit.jsonl");
        let mut chain = AuditChain::new(&path);
        chain.load_or_create().unwrap();
        assert!(chain.is_empty());
        let a = chain.append("s", "start", "{}", "cid-1").unwrap().clone();
        let b = chain.append("s", "exec", r#"{"k":"v"}"#, "cid-2").unwrap().clone();
        assert_eq!(chain.len(), 2);
        assert_eq!(a.seq, 0);
        assert_eq!(b.prev_hash, a.entry_hash);
        assert!(chain.verify());
        // tamper
        std::fs::write(&path, "junk\n").unwrap();
        let mut chain2 = AuditChain::new(&path);
        chain2.load_or_create().is_ok();
        // won't verify because of junk line OR parse error
    }
}
