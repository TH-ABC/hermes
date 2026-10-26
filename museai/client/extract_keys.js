/**
 * Muse.ai Key Extraction Tool
 * Run this snippet in the Chrome DevTools Console on https://muse.ai/
 * to export your session credentials and CVM RV key for the standalone client.
 */

(async function extractMuseKeys() {
  console.log("=== MUSE.AI CREDENTIALS EXTRACTOR ===");

  const result = {
    cookies: document.cookie,
    localStorage: { ...localStorage },
    vmId: null,
    rvKeyHex: null,
    ownerId: null,
    sessionBindingId: null
  };

  // 1. Try to read IndexedDB hatch-cvm-credentials
  try {
    const db = await new Promise((resolve, reject) => {
      const req = indexedDB.open("hatch-cvm-credentials", 1);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    const tx = db.transaction("keys", "readonly");
    const store = tx.objectStore("keys");
    const record = await new Promise((resolve, reject) => {
      const req = store.get("vesta-recovery-secret");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    if (record) {
      result.ownerId = record.ownerId;
      result.sessionBindingId = record.sessionBindingId;
      console.log("[+] Found Vesta recovery secret in IndexedDB for owner:", record.ownerId);

      // Look up active VM expectation
      const activeVmRecord = await new Promise((resolve) => {
        const req = store.get(`active-vm-expectation:${record.ownerId}`);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve(null);
      });

      if (activeVmRecord && activeVmRecord.vmId) {
        result.vmId = activeVmRecord.vmId;
        console.log("[+] Active VM ID:", result.vmId);

        // Derive CVM RV Key (krv)
        const info = new TextEncoder().encode(`hatch:rv-luks:v1:${result.vmId}`);
        const rvKeyBits = await crypto.subtle.deriveBits(
          { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(0), info },
          record.recoveryKey,
          256
        );
        const rvKeyBytes = new Uint8Array(rvKeyBits);
        result.rvKeyHex = Array.from(rvKeyBytes).map(b => b.toString(16).padStart(2, '0')).join('');
        console.log("[+] Successfully derived CVM RV Key (krv)!");
      }
    } else {
      console.log("[-] No vesta-recovery-secret found in IndexedDB (Standard VM mode)");
    }
  } catch (err) {
    console.warn("[!] Error reading IndexedDB credentials:", err);
  }

  console.log("\n================ COPY CONFIG JSON BELOW ================\n");
  console.log(JSON.stringify(result, null, 2));
  console.log("\n========================================================\n");
  return result;
})();
