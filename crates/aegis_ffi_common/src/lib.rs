//! aegis_ffi_common — Shared types for the Rust FFI boundary.
//!
//! Prompt 02: defines the minimum stable types used across crates + Python boundary.
//! Future prompts may add more; NEVER break the PyO3 signatures here.

#![forbid(unsafe_code)]

use std::fmt;

/// Shared Aegis correlation-id compatible 128-bit id. Python sees it as UUID via PyO3 later.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct AegisId(pub [u8; 16]);

impl fmt::Display for AegisId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
            self.0[0], self.0[1], self.0[2], self.0[3],
            self.0[4], self.0[5], self.0[6], self.0[7],
            self.0[8], self.0[9], self.0[10], self.0[11],
            self.0[12], self.0[13], self.0[14], self.0[15],
        )
    }
}

impl AegisId {
    pub fn new_v4() -> Self {
        use rand::RngCore;
        let mut bytes = [0u8; 16];
        rand::thread_rng().fill_bytes(&mut bytes);
        // RFC 9562 UUID v4: variant 8xxx and time_hi version 4
        bytes[6] = (bytes[6] & 0x0f) | 0x40;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        AegisId(bytes)
    }
}

/// Shared error type for all crates — keeps errors typed across the FFI boundary.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FfiError {
    InvalidArgument(String),
    Crypto(String),
    AuditChain(String),
    Internal(String),
}

impl fmt::Display for FfiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            FfiError::InvalidArgument(m) => write!(f, "invalid argument: {m}"),
            FfiError::Crypto(m) => write!(f, "crypto: {m}"),
            FfiError::AuditChain(m) => write!(f, "audit_chain: {m}"),
            FfiError::Internal(m) => write!(f, "internal: {m}"),
        }
    }
}

impl std::error::Error for FfiError {}

pub type FfiResult<T> = Result<T, FfiError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn id_v4_has_correct_version() {
        let id = AegisId::new_v4();
        // version nibble = 0100
        assert_eq!(id.0[6] >> 4, 0x4);
        // variant = 10xx
        assert_eq!(id.0[8] >> 6, 0x2);
    }
}
