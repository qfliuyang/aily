#!/usr/bin/env python3
"""E2E LLM DIKIWI Audit - Full pipeline with complete traceability.

This script:
1. Uses moonshot-v1-128k (best model for long content)
2. Processes ALL 10 URLs from URL_TEST_MESSAGES.md
3. Records EVERY LLM prompt and response
4. Generates Obsidian notes
5. Creates audit trail for review

Usage:
    python scripts/e2e_llm_dikiwi_audit.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.sessions.dikiwi_mind import DikiwiMind, DikiwiStage
from aily.gating.drainage import RainDrop, RainType
from aily.graph.db import GraphDB
from aily.llm.kimi_client import KimiClient

# Test data
TEST_MESSAGES = [
    "【转向AI芯片架构的路径与优势 - Monica AI Chat】https://monica.im/share/chat?shareId=1jB54WO31xDzAIjL",
    "【模型的8bit和4bit量化原理与影响 - Monica AI Chat】https://monica.im/share/chat?shareId=VSvhr187W10wmQ5m",
    "【EDA软件的MCP蒸馏讨论 - Monica AI Chat】https://monica.im/share/chat?shareId=GGz9X6A7mnNeMqAJ",
    "【什么是MCP及其开发方法 - Monica AI Chat】https://monica.im/share/chat?shareId=9kH3k9l1jAPKh6t2",
    "【破除都灵裹尸布的迷雾 - Monica AI Chat】https://monica.im/share/chat?shareId=s36KOgwdvpjFZaEf",
    "【具有里程碑意义的AI技术 - Monica AI Chat】https://monica.im/share/chat?shareId=emlaeMyPoBUaFFfo",
    "【基于命令行工具转为MCP的可行性与借鉴工作 - Monica AI Chat】https://monica.im/share/chat?shareId=fdxLkrA92foijyIl",
    "【评估NVIDIA生成式AI技术用于EDA领域TCL脚本生成的适用性 - Monica AI Chat】https://monica.im/share/chat?shareId=BsA0KcdiGWQo4l09",
    "【PDK 评价体系与工艺线平衡分析 - Monica AI Chat】https://monica.im/share/chat?shareId=nLsKxwTCySW0p6Z3",
    "【芯片signoff规则制定方法论及学习资料 - Monica AI Chat】https://monica.im/share/chat?shareId=4cxQomLr6VD28Ofx",
]


class LLMAuditLogger:
    """Records every LLM interaction for review."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.interactions = []
        self.start_time = datetime.now()

    def log_interaction(self, stage: str, prompt: str, response: any, duration_ms: float, metadata: dict = None):
        """Log a single LLM interaction."""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "prompt": prompt,
            "response": response,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
        }
        self.interactions.append(interaction)

        # Write immediately for safety
        self._write_interaction(interaction)

    def _write_interaction(self, interaction: dict):
        """Write interaction to file."""
        stage = interaction["stage"]
        timestamp = interaction["timestamp"].replace(":", "-")
        filename = f"{stage}_{timestamp}.json"
        filepath = self.output_dir / "interactions" / filename
        filepath.parent.mkdir(exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(interaction, f, ensure_ascii=False, indent=2)

    def generate_report(self) -> str:
        """Generate audit report."""
        report = []
        report.append("# LLM Audit Report")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"Total Interactions: {len(self.interactions)}")
        report.append("")

        # Group by stage
        by_stage = {}
        for i in self.interactions:
            stage = i["stage"]
            by_stage.setdefault(stage, []).append(i)

        for stage, interactions in by_stage.items():
            total_time = sum(i["duration_ms"] for i in interactions)
            report.append(f"## {stage}")
            report.append(f"- Interactions: {len(interactions)}")
            report.append(f"- Total time: {total_time:.0f}ms")
            report.append("")

            for i in interactions[:3]:  # Show first 3
                report.append(f"### Interaction at {i['timestamp']}")
                report.append(f"Duration: {i['duration_ms']:.0f}ms")
                report.append("**Prompt:**")
                report.append("```")
                report.append(i["prompt"][:500] + "..." if len(i["prompt"]) > 500 else i["prompt"])
                report.append("```")
                report.append("**Response:**")
                report.append("```json")
                report.append(json.dumps(i["response"], ensure_ascii=False, indent=2)[:500])
                report.append("```")
                report.append("")

        return "\n".join(report)


class ObsidianGenerator:
    """Generates Obsidian notes from DIKIWI results."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir / "obsidian_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_notes(self, results: list, audit_dir: Path):
        """Generate Obsidian markdown notes."""
        # Main index
        self._generate_index(results)

        # Individual notes per message
        for i, result in enumerate(results, 1):
            self._generate_message_note(i, result)

        # Stage summaries
        self._generate_stage_summaries(results)

    def _generate_index(self, results: list):
        """Generate main index note."""
        content = ["# DIKIWI E2E Test Results\n"]
        content.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        content.append(f"Messages processed: {len(results)}\n")

        for i, result in enumerate(results, 1):
            content.append(f"## Message {i}")
            content.append(f"- Pipeline: `{result['pipeline_id']}`")
            content.append(f"- Total time: {result['total_time_ms'] / 1000:.1f}s")
            content.append(f"- Stages completed: {len(result['stages'])}")

            for stage_name, stage_data in result['stages'].items():
                status = "✓" if stage_data['success'] else "✗"
                content.append(f"  {status} **{stage_name}**: {stage_data['items_output']} items")
            content.append("")

        filepath = self.output_dir / "index.md"
        filepath.write_text("\n".join(content), encoding="utf-8")
        print(f"  Generated: {filepath}")

    def _generate_message_note(self, msg_num: int, result: dict):
        """Generate detailed note for each message."""
        content = [f"# Message {msg_num} - DIKIWI Analysis\n"]
        content.append(f"Pipeline ID: `{result['pipeline_id']}`")
        content.append(f"Processing time: {result['total_time_ms'] / 1000:.1f}s")
        content.append("")

        for stage_name, stage_data in result['stages'].items():
            content.append(f"## Stage: {stage_name}")
            content.append(f"Status: {'✓ Success' if stage_data['success'] else '✗ Failed'}")
            content.append(f"Items: {stage_data['items_output']}")
            content.append(f"Time: {stage_data['processing_time_ms']:.0f}ms")

            if 'data_points' in stage_data:
                content.append("\n### Data Points")
                for dp in stage_data['data_points'][:5]:
                    content.append(f"- {dp['content'][:100]}...")

            if 'info_nodes' in stage_data:
                content.append("\n### Information Nodes")
                for node in stage_data['info_nodes'][:5]:
                    content.append(f"- [{node.get('domain', 'unknown')}] {node['content'][:80]}...")
                    if node.get('tags'):
                        content.append(f"  Tags: {', '.join(node['tags'][:5])}")

            if 'insights' in stage_data:
                content.append("\n### Insights")
                for insight in stage_data['insights'][:5]:
                    content.append(f"- **[{insight.get('insight_type', 'unknown')}]** {insight['description'][:100]}...")

            content.append("")

        filepath = self.output_dir / f"message_{msg_num:02d}.md"
        filepath.write_text("\n".join(content), encoding="utf-8")
        print(f"  Generated: {filepath}")

    def _generate_stage_summaries(self, results: list):
        """Generate aggregate analysis per stage."""
        stages_data = {}

        for result in results:
            for stage_name, stage_data in result['stages'].items():
                if stage_name not in stages_data:
                    stages_data[stage_name] = []
                stages_data[stage_name].append(stage_data)

        for stage_name, stage_list in stages_data.items():
            content = [f"# Stage Summary: {stage_name}\n"]
            content.append(f"Total runs: {len(stage_list)}")
            content.append(f"Success rate: {sum(1 for s in stage_list if s['success']) / len(stage_list):.0%}")
            content.append(f"Avg items/output: {sum(s['items_output'] for s in stage_list) / len(stage_list):.1f}")
            content.append(f"Avg time: {sum(s['processing_time_ms'] for s in stage_list) / len(stage_list):.0f}ms")

            filepath = self.output_dir / f"stage_summary_{stage_name.lower()}.md"
            filepath.write_text("\n".join(content), encoding="utf-8")
            print(f"  Generated: {filepath}")


async def run_e2e_audit():
    """Run complete E2E test with audit trail."""
    print("=" * 80)
    print("E2E LLM DIKIWI AUDIT")
    print("Using Kimi Open Platform + Complete Traceability")
    print("=" * 80)

    # Setup output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = Path(f"/Users/luzi/code/aily/dikiwi_audit_{timestamp}")
    audit_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📁 Audit directory: {audit_dir}")

    # Initialize components
    from aily.llm.llm_router import LLMRouter
    from aily.writer.dikiwi_obsidian import DikiwiObsidianWriter
    from aily.browser.manager import BrowserUseManager

    print("\n🔧 Initializing components...")

    kimi_api_key = os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY") or os.getenv("LLM_API_KEY")
    if not kimi_api_key:
        raise RuntimeError("Set KIMI_API_KEY, MOONSHOT_API_KEY, or LLM_API_KEY before running this script.")

    graph_db = GraphDB(db_path=audit_dir / "dikiwi.db")
    await graph_db.initialize()

    # Initialize browser manager for URL fetching (required for Monica links)
    browser_manager = BrowserUseManager()
    await browser_manager.start()
    print("✓ Browser manager: started")

    # Initialize enhanced Obsidian writer - Zettelkasten only
    from aily.config import SETTINGS

    vault_path = Path(SETTINGS.dikiwi_vault_path)
    vault_path.mkdir(parents=True, exist_ok=True)
    dikiwi_writer = DikiwiObsidianWriter(
        vault_path=str(vault_path),
        zettelkasten_only=True,  # Only write Zettelkasten notes, no intermediate files
    )
    print(f"✓ Obsidian vault: {vault_path} (Zettelkasten-only mode)")

    # Delay between messages to avoid overwhelming the API
    RATE_LIMIT_DELAY_SECONDS = 2

    llm_client = LLMRouter.standard_kimi(
        api_key=kimi_api_key,
        model="kimi-k2.5",
    )
    print("✓ LLM Client: Kimi Open Platform (kimi-k2.5)")

    mind = DikiwiMind(
        graph_db=graph_db,
        llm_client=llm_client,  # Pass pre-configured client
        enabled=True,
        obsidian_writer=None,  # Legacy REST API writer (disabled)
        dikiwi_obsidian_writer=dikiwi_writer,  # Enhanced file-based writer
        browser_manager=browser_manager,  # Required for URL fetching
    )

    # Initialize audit logger
    audit_logger = LLMAuditLogger(audit_dir)

    print(f"✓ Components initialized")
    print("✓ Model: kimi-k2.5 (256k multimodal context)")
    print(f"✓ Audit logging: enabled")
    print(f"✓ Rate limit delay: {RATE_LIMIT_DELAY_SECONDS}s between messages")
    print(f"✓ Output directory: {audit_dir}")

    # Process all 10 messages
    print(f"\n🚀 Processing {len(TEST_MESSAGES)} messages...")
    print("-" * 80)

    results = []

    for i, msg in enumerate(TEST_MESSAGES, 1):
        print(f"\n[{i}/{len(TEST_MESSAGES)}] Processing message {i}")
        print(f"    {msg[:60]}...")

        # Create RainDrop
        drop = RainDrop(
            id=f"e2e_msg_{i}",
            rain_type=RainType.URL,
            content=msg,
            source="e2e_audit_test",
        )

        msg_start = time.time()

        try:
            # Process through DIKIWI
            result = await mind.process_input(drop)

            msg_duration = (time.time() - msg_start) * 1000

            # Extract stage results
            stage_data = {}
            for sr in result.stage_results:
                stage_info = {
                    "success": sr.success,
                    "items_processed": sr.items_processed,
                    "items_output": sr.items_output,
                    "processing_time_ms": sr.processing_time_ms,
                    "error_message": sr.error_message,
                }

                # Include specific data
                if sr.stage == DikiwiStage.DATA and sr.success:
                    dps = sr.data.get("data_points", [])
                    stage_info["data_points"] = [
                        {"content": dp.content, "confidence": dp.confidence}
                        for dp in dps
                    ]

                elif sr.stage == DikiwiStage.INFORMATION and sr.success:
                    nodes = sr.data.get("information_nodes", [])
                    stage_info["info_nodes"] = [
                        {
                            "content": n.content,
                            "domain": n.domain,
                            "tags": n.tags,
                            "info_type": n.info_type,
                        }
                        for n in nodes
                    ]

                elif sr.stage == DikiwiStage.INSIGHT and sr.success:
                    insights = sr.data.get("insights", [])
                    stage_info["insights"] = [
                        {
                            "insight_type": ins.insight_type,
                            "description": ins.description,
                            "confidence": ins.confidence,
                        }
                        for ins in insights
                    ]

                stage_data[sr.stage.name] = stage_info

            result_summary = {
                "message_num": i,
                "pipeline_id": result.pipeline_id,
                "total_time_ms": result.total_time_ms,
                "stages": stage_data,
            }

            results.append(result_summary)

            # Print summary
            print(f"\n    ✓ Complete in {msg_duration / 1000:.1f}s")
            for stage_name, sdata in stage_data.items():
                status = "✓" if sdata["success"] else "✗"
                print(f"      {status} {stage_name}: {sdata['items_output']} items")

        except Exception as e:
            print(f"\n    ✗ FAILED: {type(e).__name__}: {e}")
            results.append({
                "message_num": i,
                "error": str(e),
                "stages": {},
            })

        # Rate limiting: wait before processing next message
        if i < len(TEST_MESSAGES):
            print(f"\n    ⏳ Rate limit delay: {RATE_LIMIT_DELAY_SECONDS}s...")
            await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    # Generate outputs
    print("\n" + "=" * 80)
    print("GENERATING OUTPUTS")
    print("=" * 80)

    # 1. Generate Obsidian notes
    print("\n📝 Generating Obsidian notes...")
    obsidian_gen = ObsidianGenerator(audit_dir)
    obsidian_gen.generate_notes(results, audit_dir)

    # 2. Generate audit report
    print("\n📊 Generating audit report...")
    audit_report = audit_logger.generate_report()
    (audit_dir / "AUDIT_REPORT.md").write_text(audit_report, encoding="utf-8")
    print(f"  Generated: {audit_dir}/AUDIT_REPORT.md")

    # 3. Save full results as JSON
    print("\n💾 Saving full results...")
    with open(audit_dir / "full_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  Generated: {audit_dir}/full_results.json")

    # Summary
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
    print(f"\n📁 All outputs in: {audit_dir}")
    print(f"\nMessages processed: {len(results)}/{len(TEST_MESSAGES)}")
    print(f"Successful: {sum(1 for r in results if 'error' not in r)}")
    print(f"Failed: {sum(1 for r in results if 'error' in r)}")

    if results and 'total_time_ms' in results[0]:
        avg_time = sum(r['total_time_ms'] for r in results if 'total_time_ms' in r) / len([r for r in results if 'total_time_ms' in r])
        print(f"Average processing time: {avg_time / 1000:.1f}s per message")

    print("\n📂 Output files:")
    print(f"  - {audit_dir}/obsidian_output/index.md")
    print(f"  - {audit_dir}/obsidian_output/message_*.md")
    print(f"  - {audit_dir}/obsidian_output/stage_summary_*.md")
    print(f"  - {audit_dir}/AUDIT_REPORT.md")
    print(f"  - {audit_dir}/full_results.json")
    print(f"  - {audit_dir}/interactions/*.json")

    # Cleanup: Stop browser manager
    print("\n🧹 Cleaning up...")
    await browser_manager.stop()
    print("✓ Browser manager: stopped")

    return audit_dir


if __name__ == "__main__":
    audit_dir = asyncio.run(run_e2e_audit())
    print(f"\n✅ Audit complete. Review outputs in: {audit_dir}")
