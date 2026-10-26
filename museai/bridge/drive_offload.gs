// Deploy: script.google.com → New project → paste → Project Settings → Script
// properties: add SECRET (a long random string, same as DRIVE_WEBAPP_SECRET on
// the server). Deploy → New deployment → Web app → Execute as: Me,
// Who has access: Anyone. Files stay PRIVATE in your Drive.

function doPost(e) {
  try {
    const p = JSON.parse(e.postData.contents);
    const secret = PropertiesService.getScriptProperties().getProperty("SECRET");
    if (!secret || p.secret !== secret) return _json({ error: "forbidden" });

    if (p.action === "upload") {
      const blob = Utilities.newBlob(Utilities.base64Decode(p.data), p.mime || "video/mp4", p.name || "clip.mp4");
      const folder = p.folderId ? DriveApp.getFolderById(p.folderId) : DriveApp.getRootFolder();
      const f = folder.createFile(blob);
      return _json({ ok: true, fileId: f.getId(), size: f.getSize() });
    }
    if (p.action === "download") {
      const f = DriveApp.getFileById(p.fileId);
      const b = f.getBlob();
      return _json({ ok: true, mime: b.getContentType(), data: Utilities.base64Encode(b.getBytes()) });
    }
    if (p.action === "delete") {
      DriveApp.getFileById(p.fileId).setTrashed(true);
      return _json({ ok: true });
    }
    return _json({ error: "unknown_action" });
  } catch (err) {
    return _json({ error: String(err.message || err) });
  }
}

function _json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
