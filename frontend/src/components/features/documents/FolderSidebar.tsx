"use client";

/**
 * FolderSidebar — shows folders in the Documents page.
 * Provides folder creation, navigation, and document-to-folder assignment.
 */

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Folder, FolderOpen, FolderPlus, MoreHorizontal, Pencil, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { listAllFolders, createFolder, renameFolder, deleteFolder, type Folder as FolderType } from "@/lib/api/folders";

interface FolderSidebarProps {
  selectedFolderId: string | null;
  onSelectFolder: (folderId: string | null) => void;
  onFoldersChanged?: () => void;
}

export function FolderSidebar({ selectedFolderId, onSelectFolder, onFoldersChanged }: FolderSidebarProps) {
  const [folders, setFolders] = useState<FolderType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listAllFolders();
      setFolders(result.items ?? []);
    } catch { setFolders([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await createFolder(newName.trim());
      setNewName(""); setShowCreate(false);
      await refresh();
      onFoldersChanged?.();
    } catch { /* ignore */ }
  };

  const handleRename = async (id: string) => {
    if (!editName.trim()) return;
    try {
      await renameFolder(id, editName.trim());
      setEditingId(null); setEditName("");
      await refresh();
      onFoldersChanged?.();
    } catch { /* ignore */ }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this folder?\n\nDocuments inside will NOT be deleted.")) return;
    try {
      await deleteFolder(id);
      if (selectedFolderId === id) onSelectFolder(null);
      await refresh();
      onFoldersChanged?.();
    } catch { /* ignore */ }
  };

  // Build tree structure
  const topLevel = folders.filter((f) => !f.parent_id);
  const childrenOf = (parentId: string) => folders.filter((f) => f.parent_id === parentId);

  const FolderItem = ({ folder, depth = 0 }: { folder: FolderType; depth?: number }) => {
    const children = childrenOf(folder.id);
    const isSelected = selectedFolderId === folder.id;
    const [expanded, setExpanded] = useState(true);

    return (
      <div>
        <div
          className={cn(
            "group flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm cursor-pointer transition-colors",
            isSelected ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          )}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => onSelectFolder(folder.id)}
        >
          {children.length > 0 ? (
            <button type="button" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
              className="shrink-0 p-0.5 rounded hover:bg-[var(--bg-hover)]">
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            </button>
          ) : <span className="w-4" />}

          {isSelected ? <FolderOpen className="h-4 w-4 shrink-0" /> : <Folder className="h-4 w-4 shrink-0" />}

          {editingId === folder.id ? (
            <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void handleRename(folder.id); if (e.key === "Escape") setEditingId(null); }}
              onBlur={() => void handleRename(folder.id)}
              className="flex-1 min-w-0 rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] px-1.5 py-0.5 text-sm"
              autoFocus onClick={(e) => e.stopPropagation()} />
          ) : (
            <span className="flex-1 min-w-0 truncate">{folder.name}</span>
          )}

          {folder.document_count > 0 && (
            <span className="shrink-0 text-xs text-[var(--text-tertiary)]">{folder.document_count}</span>
          )}

          <div className="relative shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <button type="button" onClick={(e) => { e.stopPropagation(); setMenuOpen(menuOpen === folder.id ? null : folder.id); }}
              className="rounded p-0.5 hover:bg-[var(--bg-hover)]">
              <MoreHorizontal className="h-3.5 w-3.5" />
            </button>
            {menuOpen === folder.id && (
              <div className="absolute right-0 top-6 z-10 w-36 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-lg py-1">
                <button type="button" onClick={() => { setEditingId(folder.id); setEditName(folder.name); setMenuOpen(null); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--bg-hover)]">
                  <Pencil className="h-3 w-3" /> Rename
                </button>
                <button type="button" onClick={() => { void handleDelete(folder.id); setMenuOpen(null); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-[var(--danger)] hover:bg-[var(--danger-subtle)]">
                  <Trash2 className="h-3 w-3" /> Delete
                </button>
              </div>
            )}
          </div>
        </div>
        {expanded && children.map((child) => <FolderItem key={child.id} folder={child} depth={depth + 1} />)}
      </div>
    );
  };

  return (
    <div className="w-56 shrink-0 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--text-tertiary)]">Folders</h3>
        <button type="button" onClick={() => setShowCreate(!showCreate)}
          className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          title="New folder">
          <FolderPlus className="h-4 w-4" />
        </button>
      </div>

      {/* Create folder */}
      {showCreate && (
        <div className="flex gap-1.5">
          <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void handleCreate(); if (e.key === "Escape") setShowCreate(false); }}
            placeholder="Folder name" autoFocus
            className="flex-1 rounded border border-[var(--border-subtle)] bg-[var(--bg-app)] px-2 py-1 text-sm" />
          <button type="button" onClick={() => setShowCreate(false)}
            className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)]">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* All Documents */}
      <div
        className={cn(
          "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm cursor-pointer transition-colors",
          selectedFolderId === null ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        )}
        onClick={() => onSelectFolder(null)}
      >
        <Folder className="h-4 w-4" />
        <span>All Documents</span>
      </div>

      {/* Folder tree */}
      {loading ? (
        <div className="space-y-1">{[1, 2, 3].map((i) => <div key={i} className="h-8 animate-pulse rounded bg-[var(--bg-hover)]" />)}</div>
      ) : topLevel.length > 0 ? (
        <div className="space-y-0.5">
          {topLevel.map((folder) => <FolderItem key={folder.id} folder={folder} />)}
        </div>
      ) : (
        <p className="text-xs text-[var(--text-tertiary)] px-2">No folders yet. Create one to organize your documents.</p>
      )}
    </div>
  );
}
