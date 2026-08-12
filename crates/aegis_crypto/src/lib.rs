//! aegis_crypto — Rust-side hot-path crypto used by AEGIS L2.
//!
//! Implements:
//!   - sha256_hex(bytes) -> lowercase hex string
//!   - hmac_sha256_hex(key, data) -> lowercase hex string
//!   - aes256gcm_encrypt(key32, nonce12, aad, plaintext) -> ciphertext+tag
//!   - aes256gcm_decrypt(key32, nonce12, aad, ciphertext+tag) -> plaintext
//!
//! `pyo3` feature (optional) exposes these as a Python extension module
//! built by maturin when the Rust toolchain is installed.
//! Until then, Python uses the pure-Python cryptography fallback (ADR-P02-001).

#![forbid(unsafe_code)]

use aegis_ffi_common::{FfiError, FfiResult};
use aes_gcm::{
    aead::{Aead, KeyInit},
    aes_gcm::AesGcm,
    Aes256Gcm, Key, Nonce,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use hmac::{Hmac, Mac};
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
    let mut mac = Hmac::<Sha256>::new_from_slice(key)
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
    let k = validated_key(key)?;
    let n = validated_nonce(nonce)?;
    let cipher = Aes256Gcm::new(&k);
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
    let k = validated_key(key)?;
    let n = validated_nonce(nonce)?;
    let cipher = Aes256Gcm::new(&k);
    cipher
        .decrypt(&n, aes_gcm::aead::Payload { msg: ciphertext_and_tag, aad })
        .map_err(|e| FfiError::Crypto(format!("aes256gcm decrypt/auth failed: {e}")))
}

// ---------------------------------------------------------------------------
// Base64 helpers (for future key-encoding support)
// ---------------------------------------------------------------------------

/// Encode bytes as standard base64.
pub fn base64_encode(data: &[u8]) -> String {
    B64.encode(data)
}

/// Decode standard base64. Returns Err on malformed input.
pub fn base64_decode(s: &str) -> FfiResult<Vec<u8>> {
    B64.decode(s).map_err(|e| FfiError::Crypto(format!("base64 decode: {e}")))
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

fn hex_encode(bytes: &[u8]) -> String {
    const HEX_CHARS: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX_CHARS[(b >> 4) as usize] as char);
        out.push(HEX_CHARS[(b & 0x0f) as usize] as char);
    }
    out
}

fn validated_key(key: &[u8]) -> FfiResult<Key<Aes256Gcm>> {
    if key.len() != 32 {
        return Err(FfiError::Crypto(format!(
            "AES-256-GCM key must be 32 bytes, got {}",
            key.len()
        )));
    }
    Ok(*Key::<Aes256Gcm>::from_slice(key))
}

fn validated_nonce(nonce: &[u8]) -> FfiResult<aes_gcm::Nonce<aes_gcm::aead::generic_array::typenum::U12>> {
    if nonce.len() != 12 {
        return Err(FfiError::Crypto(format!(
            "AES-256-GCM nonce must be 12 bytes, got {}",
            nonce.len()
        )));
    }
    Ok(*Nonce::from_slice(nonce))
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
        // echo -n "abc" | sha256sum => ba7816bf...
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2ec73b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn sha256_empty() {
        // echo -n "" | sha256sum => e3b0c442...
        assert_eq!(
            sha256_hex(b""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn hmac_sha256_basic() {
        // HMAC-SHA256 with known key/message
        let result = hmac_sha256_hex(b"key", b"The quick brown fox jumps over the lazy dog");
        assert!(result.is_ok());
        assert_eq!(result.unwrap().len(), 64);
    }

    #[test]
    fn hmac_invalid_key() {
        // Empty key is technically allowed by HMAC (padded), non-zero len key is needed
        // Actually HMAC-SHA256 accepts any key length; this just ensures no panic
        let result = hmac_sha256_hex(b"", b"data");
        assert!(result.is_ok());
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
