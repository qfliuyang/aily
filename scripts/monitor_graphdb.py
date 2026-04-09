#!/usr/bin/env python3
"""GraphDB Monitor - Live E2E testing tool for GraphDB changes."""

import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# GraphDB path
DB_PATH = Path.home() / ".aily" / "aily_graph.db"

def get_connection():
    """Get SQLite connection to GraphDB."""
    if not DB_PATH.exists():
        return None
    return sqlite3.connect(DB_PATH)

def query_stats(conn):
    """Query current database stats."""
    cursor = conn.cursor()
    
    # Count nodes
    cursor.execute("SELECT COUNT(*) FROM nodes")
    node_count = cursor.fetchone()[0]
    
    # Count edges
    cursor.execute("SELECT COUNT(*) FROM edges")
    edge_count = cursor.fetchone()[0]
    
    # Get last 5 nodes
    cursor.execute("""
        SELECT id, type, label, source, created_at 
        FROM nodes 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    last_nodes = cursor.fetchall()
    
    # Get last 5 edges
    cursor.execute("""
        SELECT id, source_node_id, target_node_id, relation_type, created_at 
        FROM edges 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    last_edges = cursor.fetchall()
    
    # Get node type distribution
    cursor.execute("""
        SELECT type, COUNT(*) as count 
        FROM nodes 
        GROUP BY type 
        ORDER BY count DESC
    """)
    type_distribution = cursor.fetchall()
    
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "last_nodes": last_nodes,
        "last_edges": last_edges,
        "type_distribution": type_distribution
    }

def format_timestamp():
    return datetime.now().strftime("%H:%M:%S")

def print_report(stats, prev_stats=None):
    """Print formatted report."""
    print(f"\n{'='*60}")
    print(f"GraphDB Monitor Report - {format_timestamp()}")
    print(f"{'='*60}")
    print(f"Database: {DB_PATH}")
    print(f"{'='*60}")
    
    if stats is None:
        print("Database not found - waiting for creation...")
        return
    
    # Node count with delta
    node_delta = ""
    if prev_stats:
        delta = stats["node_count"] - prev_stats["node_count"]
        if delta > 0:
            node_delta = f" (+{delta} NEW)"
        elif delta < 0:
            node_delta = f" ({delta})"
    print(f"\nTotal Nodes: {stats['node_count']}{node_delta}")
    
    # Edge count with delta
    edge_delta = ""
    if prev_stats:
        delta = stats["edge_count"] - prev_stats["edge_count"]
        if delta > 0:
            edge_delta = f" (+{delta} NEW)"
        elif delta < 0:
            edge_delta = f" ({delta})"
    print(f"Total Edges: {stats['edge_count']}{edge_delta}")
    
    # Node type distribution
    print(f"\n--- Node Type Distribution ---")
    for node_type, count in stats["type_distribution"]:
        print(f"  {node_type}: {count}")
    
    # Last 5 nodes
    print(f"\n--- Last 5 Nodes ---")
    if stats["last_nodes"]:
        for node in stats["last_nodes"]:
            node_id, node_type, label, source, created_at = node
            print(f"  [{created_at}] {node_type}: {label[:50]}... (id: {node_id[:20]}...)")
    else:
        print("  No nodes found")
    
    # Last 5 edges
    print(f"\n--- Last 5 Edges ---")
    if stats["last_edges"]:
        for edge in stats["last_edges"]:
            edge_id, src, tgt, rel_type, created_at = edge
            print(f"  [{created_at}] {rel_type}: {src[:15]}... -> {tgt[:15]}...")
    else:
        print("  No edges found")
    
    # Alert for new activity
    if prev_stats:
        new_nodes = stats["node_count"] - prev_stats["node_count"]
        new_edges = stats["edge_count"] - prev_stats["edge_count"]
        if new_nodes > 0 or new_edges > 0:
            print(f"\n{'!'*60}")
            print(f"ALERT: Database changed! +{new_nodes} nodes, +{new_edges} edges")
            print(f"{'!'*60}")

async def monitor(interval=10):
    """Main monitoring loop."""
    print(f"GraphDB Monitor Started")
    print(f"Database path: {DB_PATH}")
    print(f"Polling interval: {interval}s")
    print(f"Press Ctrl+C to stop")
    print(f"{'='*60}")
    
    prev_stats = None
    
    try:
        while True:
            conn = get_connection()
            if conn:
                try:
                    stats = query_stats(conn)
                    print_report(stats, prev_stats)
                    prev_stats = stats
                finally:
                    conn.close()
            else:
                print_report(None, prev_stats)
            
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n{'='*60}")
        print("Monitor stopped by user")
        print(f"{'='*60}")

if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(monitor(interval))
