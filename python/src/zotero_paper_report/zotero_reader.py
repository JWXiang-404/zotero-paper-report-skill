"""SQLite read-only queries for Zotero database.

All queries use parameterized statements. The database is opened read-only —
this module never modifies the Zotero database.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── data classes ───────────────────────────────────────────────


@dataclass
class CollectionInfo:
    collection_id: int
    name: str
    key: str
    parent_id: int | None = None


@dataclass
class ItemInfo:
    item_id: int
    key: str
    title: str
    authors: str = ""
    year: str = ""
    abstract: str = ""
    doi: str = ""
    url: str = ""
    publication_title: str = ""
    item_type: str = ""
    has_pdf: bool = False
    pdf_path: str | None = None
    has_report: bool = False
    collection_name: str = ""


@dataclass
class DryRunResult:
    """Result of a dry-run: lists items without generating reports."""
    collections: list[CollectionInfo] = field(default_factory=list)
    items: list[ItemInfo] = field(default_factory=list)
    to_generate: list[ItemInfo] = field(default_factory=list)
    skipped_existing: list[ItemInfo] = field(default_factory=list)
    skipped_no_pdf: list[ItemInfo] = field(default_factory=list)


# ── reader ─────────────────────────────────────────────────────


class ZoteroReader:
    """Read-only SQLite queries against the Zotero database."""

    # Item types considered "academic papers"
    ACADEMIC_TYPES = (
        "journalArticle",
        "conferencePaper",
        "preprint",
        "bookSection",
        "report",
        "thesis",
        "manuscript",
    )

    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        """Open a read-only connection.

        Tries the primary database first. If it's locked (Zotero is running),
        falls back to the backup copy if available.
        """
        # Try primary database with immutable flag (no locks for reads)
        try:
            conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro&immutable=1", uri=True
            )
            conn.row_factory = sqlite3.Row
            conn.execute("SELECT 1")
            return conn
        except sqlite3.OperationalError:
            pass

        # Fallback: try backup if available
        backup_path = self.db_path + ".bak"
        if backup_path != self.db_path:
            import os
            if os.path.exists(backup_path):
                conn = sqlite3.connect(
                    f"file:{backup_path}?mode=ro", uri=True
                )
                conn.row_factory = sqlite3.Row
                return conn

        # Last resort: try primary without immutable flag
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ── collection queries ─────────────────────────────────────

    def get_top_level_collections(self) -> list[CollectionInfo]:
        """Return all top-level collections (parentCollectionID IS NULL)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT collectionID, collectionName, key, parentCollectionID "
                "FROM collections WHERE parentCollectionID IS NULL "
                "ORDER BY collectionName"
            ).fetchall()
        return [CollectionInfo(r[0], r[1], r[2], r[3]) for r in rows]

    def find_collections_by_name(self, name: str) -> list[CollectionInfo]:
        """Exact-match search for collections by name."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT collectionID, collectionName, key, parentCollectionID "
                "FROM collections WHERE collectionName = ?",
                (name,),
            ).fetchall()
        return [CollectionInfo(r[0], r[1], r[2], r[3]) for r in rows]

    def find_collections_by_name_fuzzy(self, name: str) -> list[CollectionInfo]:
        """LIKE-based search for collections by name."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT collectionID, collectionName, key, parentCollectionID "
                "FROM collections WHERE collectionName LIKE ? "
                "ORDER BY collectionName",
                (f"%{name}%",),
            ).fetchall()
        return [CollectionInfo(r[0], r[1], r[2], r[3]) for r in rows]

    def get_collection_by_key(self, key: str) -> CollectionInfo | None:
        """Get a single collection by its key."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT collectionID, collectionName, key, parentCollectionID "
                "FROM collections WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CollectionInfo(row[0], row[1], row[2], row[3])

    def get_collections_tree(
        self,
        name: str | None = None,
        key: str | None = None,
    ) -> list[CollectionInfo]:
        """Get a collection and all its descendants via recursive CTE.

        Provide either ``name`` or ``key`` to identify the root collection.
        Returns all collections in the subtree (root + descendants).
        """
        with self._connect() as conn:
            if key:
                rows = conn.execute(
                    """
                    WITH RECURSIVE tree AS (
                        SELECT collectionID, collectionName, key, parentCollectionID
                        FROM collections WHERE key = ?
                        UNION ALL
                        SELECT c.collectionID, c.collectionName, c.key, c.parentCollectionID
                        FROM collections c
                        JOIN tree t ON c.parentCollectionID = t.collectionID
                    )
                    SELECT * FROM tree
                    """,
                    (key,),
                ).fetchall()
            elif name:
                rows = conn.execute(
                    """
                    WITH RECURSIVE tree AS (
                        SELECT collectionID, collectionName, key, parentCollectionID
                        FROM collections WHERE collectionName = ?
                        UNION ALL
                        SELECT c.collectionID, c.collectionName, c.key, c.parentCollectionID
                        FROM collections c
                        JOIN tree t ON c.parentCollectionID = t.collectionID
                    )
                    SELECT * FROM tree
                    """,
                    (name,),
                ).fetchall()
            else:
                return []

        return [CollectionInfo(r[0], r[1], r[2], r[3]) for r in rows]

    # ── item queries ───────────────────────────────────────────

    def get_items_in_collections(
        self,
        collection_ids: list[int],
    ) -> list[ItemInfo]:
        """Get all academic items in the given collections."""
        if not collection_ids:
            return []

        placeholders = ",".join("?" * len(collection_ids))
        academic_placeholders = ",".join("?" * len(self.ACADEMIC_TYPES))

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT i.itemID, i.key, it.typeName
                FROM collectionItems ci
                JOIN items i ON ci.itemID = i.itemID
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                WHERE ci.collectionID IN ({placeholders})
                  AND it.typeName IN ({academic_placeholders})
                """,
                (*collection_ids, *self.ACADEMIC_TYPES),
            ).fetchall()

        items = []
        for row in rows:
            item_id, key, item_type = row[0], row[1], row[2]
            meta = self._get_item_metadata(conn, item_id)
            pdf_info = self._check_pdf(conn, item_id)
            report_info = self._check_report(conn, item_id)

            items.append(
                ItemInfo(
                    item_id=item_id,
                    key=key,
                    title=meta.get("title", "(无标题)"),
                    authors=meta.get("authors", ""),
                    year=meta.get("date", ""),
                    abstract=meta.get("abstractNote", ""),
                    doi=meta.get("DOI", ""),
                    url=meta.get("url", ""),
                    publication_title=meta.get("publicationTitle", ""),
                    item_type=item_type,
                    has_pdf=pdf_info["has_pdf"],
                    pdf_path=pdf_info.get("path"),
                    has_report=report_info,
                )
            )
        return items

    def _get_item_metadata(self, conn: sqlite3.Connection, item_id: int) -> dict[str, str]:
        """Get metadata fields for an item (EAV pattern)."""
        rows = conn.execute(
            """
            SELECT f.fieldName, idv.value
            FROM itemData id
            JOIN fieldsCombined f ON id.fieldID = f.fieldID
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.itemID = ? AND f.fieldName IN (
                'title', 'abstractNote', 'date', 'DOI', 'url', 'publicationTitle'
            )
            """,
            (item_id,),
        ).fetchall()

        meta = {r[0]: r[1] for r in rows}

        # Get authors
        author_rows = conn.execute(
            """
            SELECT c.firstName, c.lastName
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ? AND ct.creatorType = 'author'
            ORDER BY ic.orderIndex
            """,
            (item_id,),
        ).fetchall()

        if author_rows:
            names = []
            for ar in author_rows:
                first, last = ar[0] or "", ar[1] or ""
                # Zotero stores names "last, first" style; join sensibly
                if first and last:
                    names.append(f"{last}, {first}")
                elif last:
                    names.append(last)
            meta["authors"] = "; ".join(names)

        return meta

    def _check_pdf(self, conn: sqlite3.Connection, item_id: int) -> dict:
        """Check if the item has a PDF attachment."""
        rows = conn.execute(
            """
            SELECT a.path, a.contentType
            FROM itemAttachments a
            WHERE a.parentItemID = ? AND a.contentType = 'application/pdf'
            LIMIT 1
            """,
            (item_id,),
        ).fetchall()

        if rows:
            return {"has_pdf": True, "path": rows[0][0]}
        return {"has_pdf": False, "path": None}

    def _check_report(self, conn: sqlite3.Connection, item_id: int) -> bool:
        """Check if the item already has a child note tagged '文献报告'.

        Uses two strategies:
        1. Find child notes with tag "文献报告"
        2. Fallback: child notes with title containing "文献报告"
        """
        # Strategy 1: tag-based
        row = conn.execute(
            """
            SELECT 1 FROM itemNotes n
            JOIN itemTags it ON n.itemID = it.itemID
            JOIN tags t ON it.tagID = t.tagID
            WHERE n.parentItemID = ? AND t.name = '文献报告'
            LIMIT 1
            """,
            (item_id,),
        ).fetchone()

        if row:
            return True

        # Strategy 2: title-based fallback
        row = conn.execute(
            """
            SELECT 1 FROM itemNotes n
            WHERE n.parentItemID = ? AND n.title LIKE '%文献报告%'
            LIMIT 1
            """,
            (item_id,),
        ).fetchone()

        return row is not None

    # ── convenience ────────────────────────────────────────────

    def get_all_items_for_dry_run(
        self,
        collections: list[CollectionInfo],
    ) -> DryRunResult:
        """Collect all items and classify them (for --dry-run)."""
        all_items: list[ItemInfo] = []
        to_generate: list[ItemInfo] = []
        skipped_existing: list[ItemInfo] = []
        skipped_no_pdf: list[ItemInfo] = []

        for coll in collections:
            tree = self.get_collections_tree(key=coll.key)
            if not tree:
                tree = [coll]
            coll_ids = [c.collection_id for c in tree]
            items = self.get_items_in_collections(coll_ids)

            for item in items:
                # Attach collection context
                item.collection_name = coll.name
                all_items.append(item)

                if item.has_report:
                    skipped_existing.append(item)
                elif not item.has_pdf:
                    skipped_no_pdf.append(item)
                else:
                    to_generate.append(item)

        # Deduplicate by item key (same item can be in multiple collections)
        seen = set()
        deduped_all: list[ItemInfo] = []
        for item in all_items:
            if item.key not in seen:
                seen.add(item.key)
                deduped_all.append(item)

        return DryRunResult(
            collections=collections,
            items=deduped_all,
            to_generate=to_generate,
            skipped_existing=skipped_existing,
            skipped_no_pdf=skipped_no_pdf,
        )
