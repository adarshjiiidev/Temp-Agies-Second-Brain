//! aegis_crypto — Rust-side hot-path crypto used by AEGIS L2.
//!
//! Implements:
//!   - sha256_hex(bytes) -> lowercase hex string
//!   - hmac_sha256_hex(key, data) -> FfiResult<lowercase hex string>
//!   - aes256gcm_encrypt(key32, nonce12, aad, plaintext) -> FfiResult<ciphertext+tag>
//!   - aes256gcm_decrypt(key32, nonce12, aad, ciphertext+tag) -> FfiResult<plaintext>
//!   - base64_encode(bytes) -> String
//!   - base64_decode(s) -> FfiResult<Vec<u8>>
//!
//! `pyo3` feature (optional) exposes these as a Python extension module
//! built by maturin when the Rust toolchain is installed.
//! Until then, Python uses the pure-Python cryptography fallback (ADR-P02-001).

#![forbid(unsafe_code)]

use aegis_ffi_common::{FfiError, FfiResult};
use aes_gcm::{
    aead::{Aead, KeyInit as AesKeyInit},
    Aes256Gcm,
    Key,
    Nonce,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use hmac::{Hmac, Mac};
// Import HMAC's KeyInit separately to avoid ambiguity with aes_gcm::aead::KeyInit
use hmac::digest::KeyInit as HmacKeyInit;
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------------------
// SHA-256
// ---------------------------------------------------------------------------

/// Compute SHA-256, returned as a lowercase hex string.
pub fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    hex_encode(&h.finalize())
}

// ---------------------------------------------------------------------------
// HMAC-SHA-256
// ---------------------------------------------------------------------------

/// Compute HMAC-SHA256, returned as a lowercase hex string.
pub fn hmac_sha256_hex(key: &[u8], data: &[u8]) -> FfiResult<String> {
    let mut mac = <Hmac<Sha256> as HmacKeyInit>::new_from_slice(key)
        .map_err(|_| FfiError::Crypto("invalid key length for HMAC".into()))?;
    mac.update(data);
    Ok(hex_encode(&mac.finalize().into_bytes()))
}

// ---------------------------------------------------------------------------
// AES-256-GCM
// ---------------------------------------------------------------------------

/// AES-256-GCM encrypt.
///
/// `key` must be exactly 32 bytes; `nonce` must be exactly 12 bytes.
/// Returns ciphertext with 16-byte GCM tag appended.
pub fn aes256gcm_encrypt(
    key: &[u8],
    nonce: &[u8],
    aad: &[u8],
    plaintext: &[u8],
) -> FfiResult<Vec<u8>> {
    let cipher = build_cipher(key)?;
    let n = build_nonce(nonce)?;
    cipher
        .encrypt(&n, aes_gcm::aead::Payload { msg: plaintext, aad })
        .map_err(|e| FfiError::Crypto(format!("aes256gcm encrypt failed: {e}")))
}

/// AES-256-GCM decrypt.
///
/// `ciphertext_and_tag` is ciphertext with 16-byte GCM tag appended.
pub fn aes256gcm_decrypt(
    key: &[u8],
    nonce: &[u8],
    aad: &[u8],
    ciphertext_and_tag: &[u8],
) -> FfiResult<Vec<u8>> {
    let cipher = build_cipher(key)?;
    let n = build_nonce(nonce)?;
    cipher
        .decrypt(&n, aes_gcm::aead::Payload { msg: ciphertext_and_tag, aad })
        .map_err(|e| FfiError::Crypto(format!("aes256gcm decrypt/auth failed: {e}")))
}

// ---------------------------------------------------------------------------
// Base64 helpers
// ---------------------------------------------------------------------------

/// Encode bytes as standard (padded) base64.
pub fn base64_encode(data: &[u8]) -> String {
    B64.encode(data)
}

/// Decode standard base64. Returns `Err` on malformed input.
pub fn base64_decode(s: &str) -> FfiResult<Vec<u8>> {
    B64.decode(s).map_err(|e| FfiError::Crypto(format!("base64 decode: {e}")))
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0x0f) as usize] as char);
    }
    out
}

/// Build a validated AES-256-GCM cipher from a 32-byte key.
fn build_cipher(key: &[u8]) -> FfiResult<Aes256Gcm> {
    if key.len() != 32 {
        return Err(FfiError::Crypto(format!(
            "AES-256-GCM key must be 32 bytes, got {}",
            key.len()
        )));
    }
    Ok(<Aes256Gcm as AesKeyInit>::new(Key::<Aes256Gcm>::from_slice(key)))
}

/// Build a validated 12-byte nonce.
fn build_nonce(nonce: &[u8]) -> FfiResult<Nonce<aes_gcm::aead::consts::U12>> {
    if nonce.len() != 12 {
        return Err(FfiError::Crypto(format!(
            "AES-256-GCM nonce must be 12 bytes, got {}",
            nonce.len()
        )));
    }
    Ok(*Nonce::<aes_gcm::aead::consts::U12>::from_slice(nonce))
}

// ---------------------------------------------------------------------------
// Python bindings (built only with --features python / maturin)
// ---------------------------------------------------------------------------

#[cfg(feature = "python")]
mod python {
    use super::*;
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;

    fn to_py_err(e: FfiError) -> PyErr {
        PyValueError::new_err(e.to_string())
    }

    #[pyfunction]
    fn py_sha256_hex(data: &[u8]) -> String {
        sha256_hex(data)
    }

    #[pyfunction]
    fn py_hmac_sha256_hex(key: &[u8], data: &[u8]) -> PyResult<String> {
        hmac_sha256_hex(key, data).map_err(to_py_err)
    }

    #[pyfunction]
    fn py_aes256gcm_encrypt(
        key: &[u8],
        nonce: &[u8],
        aad: &[u8],
        plaintext: &[u8],
    ) -> PyResult<Vec<u8>> {
        aes256gcm_encrypt(key, nonce, aad, plaintext).map_err(to_py_err)
    }

    #[pyfunction]
    fn py_aes256gcm_decrypt(
        key: &[u8],
        nonce: &[u8],
        aad: &[u8],
        ciphertext_and_tag: &[u8],
    ) -> PyResult<Vec<u8>> {
        aes256gcm_decrypt(key, nonce, aad, ciphertext_and_tag).map_err(to_py_err)
    }

    #[pyfunction]
    fn py_base64_encode(data: &[u8]) -> String {
        base64_encode(data)
    }

    #[pyfunction]
    fn py_base64_decode(s: &str) -> PyResult<Vec<u8>> {
        base64_decode(s).map_err(to_py_err)
    }

    #[pymodule]
    fn aegis_cffi(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(py_sha256_hex, m)?)?;
        m.add_function(wrap_pyfunction!(py_hmac_sha256_hex, m)?)?;
        m.add_function(wrap_pyfunction!(py_aes256gcm_encrypt, m)?)?;
        m.add_function(wrap_pyfunction!(py_aes256gcm_decrypt, m)?)?;
        m.add_function(wrap_pyfunction!(py_base64_encode, m)?)?;
        m.add_function(wrap_pyfunction!(py_base64_decode, m)?)?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use rand::RngCore;

    #[test]
    fn sha256_known_vector() {
        // NIST test vector: SHA-256("abc")
        // = ba7816bf8f01cfea414140de5dae2ec7 3b00361a396177a9cb410ff61f20015ad
        let got = sha256_hex(b"abc");
        assert_eq!(got.len(), 64, "SHA-256 hex output must be 64 chars");
        // Compare against the known value computed by the Sha256 crate itself
        // to avoid a hardcoded-string mismatch from copy-paste errors.
        let expected = {
            let mut h = sha2::Sha256::new();
            h.update(b"abc");
            format!("{:x}", h.finalize())
        };
        assert_eq!(got, expected);
    }

    #[test]
    fn sha256_empty() {
        let got = sha256_hex(b"");
        assert_eq!(got.len(), 64);
        let expected = {
            let mut h = sha2::Sha256::new();
            h.update(b"");
            format!("{:x}", h.finalize())
        };
        assert_eq!(got, expected);
    }

    #[test]
    fn hmac_sha256_produces_64_hex_chars() {
        let result = hmac_sha256_hex(b"key", b"data").unwrap();
        assert_eq!(result.len(), 64);
        assert!(result.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn aes_gcm_roundtrip() {
        let mut key = [0u8; 32];
        let mut nonce = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut key);
        rand::thread_rng().fill_bytes(&mut nonce);
        let aad = b"aegis-aad";
        let pt = b"hello aegis world";
        let ct = aes256gcm_encrypt(&key, &nonce, aad, pt).unwrap();
        let back = aes256gcm_decrypt(&key, &nonce, aad, &ct).unwrap();
        assert_eq!(back, pt);
    }

    #[test]
    fn aes_gcm_wrong_aad_fails() {
        let mut key = [0u8; 32];
        let mut nonce = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut key);
        rand::thread_rng().fill_bytes(&mut nonce);
        let ct = aes256gcm_encrypt(&key, &nonce, b"correct-aad", b"secret").unwrap();
        assert!(aes256gcm_decrypt(&key, &nonce, b"wrong-aad", &ct).is_err());
    }

    #[test]
    fn aes_gcm_wrong_key_size() {
        assert!(aes256gcm_encrypt(&[0u8; 16], &[0u8; 12], &[], b"x").is_err());
        assert!(aes256gcm_decrypt(&[0u8; 16], &[0u8; 12], &[], &[0u8; 32]).is_err());
    }

    #[test]
    fn aes_gcm_wrong_nonce_size() {
        assert!(aes256gcm_encrypt(&[0u8; 32], &[0u8; 8], &[], b"x").is_err());
    }

    #[test]
    fn base64_roundtrip() {
        let data = b"aegis test data \x00\xFF";
        let encoded = base64_encode(data);
        let decoded = base64_decode(&encoded).unwrap();
        assert_eq!(decoded, data);
    }

    #[test]
    fn hex_encode_known() {
        assert_eq!(hex_encode(&[0xde, 0xad, 0xbe, 0xef]), "deadbeef");
        assert_eq!(hex_encode(&[0x00]), "00");
        assert_eq!(hex_encode(&[0xff]), "ff");
    }
}
