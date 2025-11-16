#!/usr/bin/env python3
"""
MCP Server for RAG Knowledge Base integration with Claude Code.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from main import RAGSystem
from processing import Embedder
from utils import log


# Initialize RAG system
rag_system = RAGSystem()
embedder = Embedder()

# Create MCP server
server = Server("rag-knowledge-base")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available MCP tools."""
    return [
        types.Tool(
            name="search_rag",
            description="Search the RAG knowledge base for relevant technical information",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query or question"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    },
                    "source_type": {
                        "type": "string",
                        "enum": ["all", "documentation", "youtube", "github"],
                        "description": "Filter by source type (default: all)",
                        "default": "all"
                    },
                    "difficulty": {
                        "type": "string",
                        "enum": ["all", "beginner", "intermediate", "advanced"],
                        "description": "Filter by difficulty level (default: all)",
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="add_source",
            description="Add sources (URLs or search prompt) to the RAG knowledge base",
            inputSchema={
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "URLs (one per line) or search prompt"
                    },
                    "process_immediately": {
                        "type": "boolean",
                        "description": "Process sources immediately (default: false)",
                        "default": False
                    }
                },
                "required": ["input"]
            }
        ),
        types.Tool(
            name="get_status",
            description="Get RAG system status and statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""

    if name == "search_rag":
        query = arguments["query"]
        n_results = arguments.get("n_results", 5)
        source_type = arguments.get("source_type", "all")
        difficulty = arguments.get("difficulty", "all")

        log.info(f"Searching RAG: '{query}' (n={n_results}, type={source_type})")

        # Build filters
        where_filter = {}
        if source_type != "all":
            # Map friendly names to internal types
            type_map = {
                "documentation": "website",
                "youtube": "youtube_video",
                "github": "github"
            }
            where_filter["source_type"] = type_map.get(source_type, source_type)

        if difficulty != "all":
            where_filter["difficulty"] = difficulty

        # Search
        results = rag_system.search(
            query=query,
            n_results=n_results,
            filters=where_filter if where_filter else None
        )

        # Format results
        if not results['documents'] or not results['documents'][0]:
            return [types.TextContent(
                type="text",
                text="No results found in the knowledge base."
            )]

        formatted_results = []
        for i, (doc, meta, distance) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results.get('distances', [[0]*len(results['documents'][0])])[0]
        )):
            score = 1 - distance if distance else 1.0
            formatted_results.append(f"""
### Result {i+1} (Score: {score:.2f})

**Source:** {meta.get('source_url', 'N/A')}
**Type:** {meta.get('source_type', 'N/A')} | **Difficulty:** {meta.get('difficulty', 'N/A')}
**Topics:** {', '.join(meta.get('topics', []))}

{doc}

---
""")

        return [types.TextContent(
            type="text",
            text="\n".join(formatted_results)
        )]

    elif name == "add_source":
        user_input = arguments["input"]
        process_immediately = arguments.get("process_immediately", False)

        log.info(f"Adding source: {user_input[:100]}...")

        # Add sources via orchestrator
        result = rag_system.add_sources(user_input)

        response_text = f"""✅ **Sources Added**

- **Input type:** {result['input_type']}
- **URLs discovered:** {result['urls_discovered']}
- **URLs added:** {result['urls_added']}
- **URLs skipped:** {result['urls_skipped']} (duplicates)
"""

        # Optionally process immediately
        if process_immediately and result['urls_added'] > 0:
            response_text += "\n🔄 **Processing sources...**\n"

            from queue_processor.integrated_processor import IntegratedProcessor
            processor = IntegratedProcessor()

            process_result = await processor.process_batch(batch_size=result['urls_added'])

            response_text += f"\n✅ **Processing complete:**\n"
            response_text += f"- Processed: {process_result['processed']}\n"
            response_text += f"- Succeeded: {process_result['succeeded']}\n"
            response_text += f"- Failed: {process_result['failed']}\n"

            processor.close()
        else:
            response_text += "\n💡 Sources added to queue. Run processing pipeline to extract content.\n"

        return [types.TextContent(
            type="text",
            text=response_text
        )]

    elif name == "get_status":
        log.info("Getting system status")

        stats = rag_system.get_stats()

        status_text = f"""📊 **RAG System Status**

**Database:**
- Total URLs: {stats['database']['total']}
- ✅ Scraped: {stats['database']['scraped']}
- ⏳ Pending: {stats['database']['pending']}
- ❌ Failed: {stats['database']['failed']}

**Vector Database:**
- Total chunks: {stats['vector_store']['total_chunks']:,}
- Collection: {stats['vector_store']['collection_name']}

**By Source Type:**
"""
        for source_type, count in stats['vector_store'].get('by_source_type', {}).items():
            status_text += f"- {source_type}: {count} chunks\n"

        return [types.TextContent(
            type="text",
            text=status_text
        )]

    else:
        return [types.TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run the MCP server."""
    log.info("Starting MCP server for RAG knowledge base")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
