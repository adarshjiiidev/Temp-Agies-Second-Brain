//! aegis_crypto — Rust-side hot-path crypto used by AEGIS L2.
//!
//! Prompt 02 FFI skeleton: mirrors Python `aegis.l2_foundation.crypto.vault.FileSecretVault`
//! and `Hasher`. Implements:
//!   - sha256_hex(bytes) -> hex
//!   - hmac_sha256_hex(key, data) -> hex
//!   - aes256gcm_encrypt(key32, nonce12, aad, plaintext -> ciphertext+tag
//!   - aes256gcm_decrypt(..) -> plaintext
//!
//! `pyo3` feature exposes these functions to Python via `aegis_cffi` extension module
//! built by maturin when Rust toolchain is installed.
//! Until then, Python uses the pure-python cryptography fallback (ADR-P02-001).

#![forbid(unsafe_code)]

use aegis_ffi_common::{FfiError, FfiResult};
use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Key, Nonce,
};
use base64::{engine::general_purpose::STANDARD as B64;
use base64::Engine as _;
use hmac::{Hmac, Mac};
use sha2::{Digest, Sha256};

/// Compute SHA-256, returned as lowercase hex string.
pub fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    let out = h.finalize();
    hex_encode(&out)
}

/// Compute HMAC-SHA256, returned as lowercase hex string.
pub fn hmac_sha256_hex(key: &[u8], data: &[u8]) -> String {
    let mut mac = Hmac::<Sha256>::new_from_slice(key)
        .map_err(|_| FfiError::Crypto("invalid key length".into()))
        .unwrap();
    mac.update(data);
    let out = mac.finalize().into_bytes();
    hex_encode(&out)
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef".as_slice().try_into().unwrap();
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as char);
        out.push(HEX[(b & 0x0f)] as char);
    }
    out
}

/// AES-256-GCM encrypt. `key` must be 32 bytes, `nonce` 12 bytes. Returns
/// ciphertext with 16-byte tag appended (matching `AesGcm convention).
pub fn aes256gcm_encrypt(
    key: &[u8],
    nonce: &[u8],
    aad: &[u8],
    plaintext: &[u8],
) -> FfiResult<Vec<u8>> {
    if key.len() != 32 {
        return Err(FfiError::Crypto("key must be 32 bytes".into()));
    }
    if nonce.len() != 12 {
        return Err(FfiError::Crypto("nonce must be 12 bytes".into()));
    }
    let k = Key::<Aes256Gcm>::from_slice(key);
    let cipher = Aes256Gcm::new(k);
    let n = Nonce::from_slice(nonce);
    cipher
        .encrypt(nonce, aad
            .iter()
            .chain(plaintext.iter())
            .copied()
            .collect::<Vec<u8>>()
            .as_slice())
        .map_err(|e| FfiError::Crypto(format!("encrypt: {e}")))
        // .map(|ct_and_tag| {
        //     // NOTE: aes-gcm returns ciphertext+tag; we also need to pass aad explicitly. The
        //     // Re-doing it cleanly by building the split call form:
        // })
        .and_then(|_bad| {
            // Re-run cleanly using proper aead API form.
            cipher
                .encrypt(n, aes_gcm::aead::Payload { msg: plaintext, aad })
                .map_err(|e| FfiError::Crypto(format!("encrypt retry: {e}")))
        })
}

/// AES-256-GCM decrypt. `ciphertext_and_tag` is ciphertext + 16-byte tag appended.
pub fn aes256gcm_decrypt(
    key: &[u8],
    nonce: &[u8],
    aad: &[u8],
    ciphertext_and_tag: &[u8],
) -> FfiResult<Vec<u8>> {
    if key.len() != 32 {
        return Err(FfiError::Crypto("key must be 32 bytes".into()));
    }
    if nonce.len() != 12 {
        return Err(FfiError::Crypto("nonce must be 12 bytes".into()));
    }
    let k = Key::<Aes256Gcm>::from_slice(key);
    let cipher = Aes256Gcm::new(k);
    let n = Nonce::from_slice(nonce);
    cipher
        .decrypt(n, aes_gcm::aead::Payload { msg: ciphertext_and_tag, aad })
        .map_err(|e| FfiError::Crypto(format!("decrypt: auth failed {e}"))
}

// -----------------------------------------------------------------------------
// Python bindings (built only with feature = ["python"].
// -----------------------------------------------------------------------------
#[cfg(feature = "python")]
mod python {
    use super::*;
    use pyo3::prelude::*;
    use pyo3::exceptions::PyValueError;

    fn to_py_err(e: FfiError) -> PyErr {
        PyValueError::new_err(e.to_string())
    }

    #[pyfunction]
    fn py_sha256_hex(data: &[u8]) -> String {
        sha256_hex(data)
    }

    #[pyfunction]
    fn py_hmac_sha256_hex(key: &[u8], data: &[u8]) -> String {
        hmac_sha256_hex(key, data)
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

    #[pymodule]
    fn aegis_cffi(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(py_sha256_hex, m)?)?;
        m.add_function(wrap_pyfunction!(py_hmac_sha256_hex, m)?)?;
        m.add_function(wrap_pyfunction!(py_aes256gcm_encrypt, m)?)?;
        m.add_function(wrap_pyfunction!(py_aes256gcm_decrypt, m)?)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::RngCore;

    #[test]
    fn sha256_known_vector() {
        // echo -n abc | sha256sum = ba7816bf...
        let got = sha256_hex(b"abc");
        assert_eq!(
            got,
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn aes_roundtrip() {
        let mut key = [0u8; 32];
        let mut nonce = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut key);
        rand::thread_rng().fill_bytes(&mut nonce);
        let aad = b"aegis-aad";
        let pt = b"hello world";
        let ct = aes256gcm_encrypt(&key, &nonce, aad, pt).unwrap();
        let back = aes256gcm_decrypt(&key, &nonce, aad, &ct).unwrap();
        assert_eq!(back, pt);
        // wrong aad -> fail
        assert!(aes256gcm_decrypt(&key, &nonce, b"wrong", &ct).is_err());
    }

    #[test]
    fn wrong_key_size() {
        assert!(aes256gcm_encrypt(&[0u8; 16], &[0u8; 12], &[], b"x").is_err());
    }
}
