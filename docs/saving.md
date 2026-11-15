# Saving, recovery and external changes

## Saving and recovery

Saving writes a sibling temporary file, flushes it, then renames it over the
original. Existing file permission bits are preserved. A content check refuses
to overwrite a file changed externally; Save As only creates new destinations.
Opening another file or creating a new buffer retains unsaved edits in its original
buffer. Close and quit offer save/discard/cancel. The palette also provides an explicit discard
confirmation. Symlink files are refused; open their targets explicitly.

Changed named and unnamed buffers share one background session recovery writer.
Every 500 ms, changed workspace state is copied into a bounded queue;
file creation, writes, and flushes run on the worker. The original files are never
autosaved. Use `:recoveries` after a crash, restore the session, then save normally.
Legacy `<filename>.dna-recovery` files can still be restored when opening a file;
new sessions no longer create these duplicate sidecars. Save failures leave the
in-memory document available.

This is still a prototype: content checking is not a filesystem lock, and saving
replaces the inode (hard links, ownership, ACLs, and extended attributes are not
preserved). Rename durability across power loss is not guaranteed. Recovery is
not a replacement for backups or version control.

## External changes and clipboard

A background worker checks open files every 250 ms. Clean buffers reload changed
text; dirty buffers retain local edits and show a disk-change indicator. `:reload`
opens a conflict prompt: R discards local edits and reloads, S offers Save As,
and K/Escape keeps the buffer. Deleted, unreadable, oversized, and invalid files
never replace buffer contents. Existing save-conflict checks remain active.

Yanking multiple selections records individual fragments. When the unchanged
clipboard is pasted into the same number of selections, each gets its matching
fragment in document order. Otherwise the clipboard text repeats at each cursor.
Overlapping fragment destinations are rejected without partial edits.
