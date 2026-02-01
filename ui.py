import base64
import json
import time
import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional, Set
from scrape import scrape_multiple
from search import get_search_results
from telegram_osint import get_telegram_results, is_telegram_configured
from llm_utils import BufferedStreamingHandler
from llm import get_llm, refine_query, filter_results, generate_summary
from utils import (
    extract_iocs,
    format_iocs_for_export,
    merge_iocs,
    validate_query
)
from tor_controller import init_tor_controller, TorController
from tor_pool import get_tor_pool
from config import (
    TOR_CONTROL_PORT,
    TOR_CONTROL_PASSWORD,
    TOR_ROTATE_INTERVAL,
    TOR_MULTI_INSTANCE,
    TOR_INSTANCE_COUNT
)

# Initialize session state
if "search_history" not in st.session_state:
    st.session_state.search_history = []
if "saved_queries" not in st.session_state:
    st.session_state.saved_queries = {}
if "statistics" not in st.session_state:
    st.session_state.statistics = {
        "total_queries": 0,
        "total_iocs": 0,
        "total_results": 0,
        "query_times": [],
        "ioc_counts": {}
    }
if "tor_controller" not in st.session_state:
    st.session_state.tor_controller = None

# Streamlit page configuration
st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
    layout="wide",
)

# Enhanced Custom CSS
st.markdown(
    """
    <style>
        .colHeight {
            max-height: 40vh;
            overflow-y: auto;
            text-align: center;
        }
        .pTitle {
            font-weight: bold;
            color: #FF4B4B;
            margin-bottom: 0.5em;
        }
        .aStyle {
            font-size: 18px;
            font-weight: bold;
            padding: 5px;
            padding-left: 0px;
            text-align: center;
        }
        .metric-card {
            background-color: rgba(28, 131, 225, 0.1);
            border: 1px solid rgba(28, 131, 225, 0.3);
            border-radius: 5px;
            padding: 1rem;
            margin: 0.5rem 0;
        }
        .ioc-badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            margin: 0.25rem;
            background-color: #FF4B4B;
            color: white;
            border-radius: 3px;
            font-size: 0.85rem;
        }
        .status-success {
            color: #00CC00;
        }
        .status-error {
            color: #FF4B4B;
        }
        .status-warning {
            color: #FFA500;
        }
        .stProgress > div > div > div {
            background-color: #FF4B4B;
        }
    </style>""",
    unsafe_allow_html=True,
)


# Helper Functions
def update_progress(progress_bar, progress_text, value: float, text: str):
    """Update progress bar and text."""
    progress_bar.progress(value)
    progress_text.text(f"{text} ({int(value * 100)}%)")


def add_to_history(query: str):
    """Add query to search history."""
    if query and query not in st.session_state.search_history:
        st.session_state.search_history.insert(0, query)
        # Keep only last 20 queries
        st.session_state.search_history = st.session_state.search_history[:20]


def update_statistics(query_time: float, ioc_count: int, result_count: int):
    """Update statistics."""
    st.session_state.statistics["total_queries"] += 1
    st.session_state.statistics["total_iocs"] += ioc_count
    st.session_state.statistics["total_results"] += result_count
    st.session_state.statistics["query_times"].append(query_time)
    # Keep only last 100 query times
    if len(st.session_state.statistics["query_times"]) > 100:
        st.session_state.statistics["query_times"] = st.session_state.statistics["query_times"][-100:]


def get_tor_status():
    """Get Tor connection status."""
    try:
        if st.session_state.tor_controller is None:
            st.session_state.tor_controller = init_tor_controller(
                control_port=TOR_CONTROL_PORT,
                control_password=TOR_CONTROL_PASSWORD
            )
        
        if st.session_state.tor_controller and st.session_state.tor_controller.is_connected():
            circuits = st.session_state.tor_controller.get_circuit_info()
            exit_node = st.session_state.tor_controller.get_exit_node_info()
            return {
                "connected": True,
                "circuit_count": len(circuits),
                "exit_node": exit_node,
                "rotation_count": st.session_state.tor_controller._rotation_count
            }
    except Exception:
        pass
    
    # Fallback: check via Tor pool
    try:
        tor_pool = get_tor_pool()
        health = tor_pool.health_check_all()
        healthy_count = sum(1 for v in health.values() if v)
        return {
            "connected": healthy_count > 0,
            "circuit_count": 0,
            "exit_node": None,
            "rotation_count": 0,
            "instances_healthy": f"{healthy_count}/{tor_pool.instance_count}"
        }
    except Exception:
        return {"connected": False, "circuit_count": 0, "exit_node": None, "rotation_count": 0}


# Sidebar
st.sidebar.title("🕵️ Robin")
st.sidebar.caption("AI-Powered Dark Web OSINT Tool")

# Settings Section
with st.sidebar.expander("⚙️ Settings", expanded=True):
    model = st.selectbox(
        "Select LLM Model",
        ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"],
        key="model_select",
    )
    threads = st.slider("Scraping Threads", 1, 16, 4, key="thread_slider")
    extract_iocs_flag = st.checkbox("Extract IOCs", value=False, key="extract_iocs")
    include_telegram = st.checkbox("Include Telegram search", value=False, key="include_telegram")
    if include_telegram and not is_telegram_configured():
        st.caption("Set TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_ENABLED=true to enable.")
    export_format = st.selectbox(
        "Export Format",
        ["Markdown", "JSON", "CSV", "All"],
        key="export_format"
    )

# Advanced Settings
with st.sidebar.expander("🔧 Advanced Settings"):
    tor_rotate = st.checkbox("Enable Circuit Rotation", value=False, key="tor_rotate")
    tor_rotate_interval = st.number_input(
        "Rotation Interval (requests)",
        min_value=1,
        max_value=50,
        value=TOR_ROTATE_INTERVAL,
        key="tor_rotate_interval"
    )
    multi_instance = st.checkbox("Multi-Instance Tor", value=TOR_MULTI_INSTANCE, key="multi_instance")
    if multi_instance:
        instance_count = st.number_input(
            "Tor Instances",
            min_value=1,
            max_value=10,
            value=TOR_INSTANCE_COUNT,
            key="instance_count"
        )

# Search History
if st.session_state.search_history:
    with st.sidebar.expander("📜 Search History"):
        for idx, hist_query in enumerate(st.session_state.search_history[:10]):
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(hist_query[:40] + "..." if len(hist_query) > 40 else hist_query, 
                            key=f"hist_{idx}", use_container_width=True):
                    st.session_state.query_to_run = hist_query
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{idx}"):
                    st.session_state.search_history.remove(hist_query)
                    st.rerun()
        if st.button("Clear History"):
            st.session_state.search_history = []
            st.rerun()

# Saved Queries
if st.session_state.saved_queries:
    with st.sidebar.expander("⭐ Saved Queries"):
        for name, saved_query in st.session_state.saved_queries.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button(name, key=f"saved_{name}", use_container_width=True):
                    st.session_state.query_to_run = saved_query
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_saved_{name}"):
                    del st.session_state.saved_queries[name]
                    st.rerun()

# Tor Status Dashboard
with st.sidebar.expander("🌐 Tor Status"):
    tor_status = get_tor_status()
    if tor_status["connected"]:
        st.success("✅ Connected")
        st.metric("Circuits", tor_status.get("circuit_count", 0))
        if "instances_healthy" in tor_status:
            st.metric("Healthy Instances", tor_status["instances_healthy"])
        if tor_status.get("exit_node"):
            exit_info = tor_status["exit_node"]
            st.caption(f"Exit Node: {exit_info.get('nickname', 'Unknown')}")
            if exit_info.get("country"):
                st.caption(f"Country: {exit_info.get('country')}")
        if tor_status.get("rotation_count", 0) > 0:
            st.caption(f"Rotations: {tor_status['rotation_count']}")
    else:
        st.error("❌ Not Connected")
        st.caption("Tor may not be running or accessible")

# Statistics
with st.sidebar.expander("📊 Statistics"):
    stats = st.session_state.statistics
    st.metric("Total Queries", stats["total_queries"])
    st.metric("Total IOCs", stats["total_iocs"])
    st.metric("Total Results", stats["total_results"])
    if stats["query_times"]:
        avg_time = sum(stats["query_times"]) / len(stats["query_times"])
        st.metric("Avg Query Time", f"{avg_time:.1f}s")

# Main UI
st.title("🕵️ Robin: Dark Web OSINT Investigation")

# Logo
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(".github/assets/robin_logo.png", width=200)

# Query Input
query_to_process = None
if "query_to_run" in st.session_state:
    query_to_process = st.session_state.query_to_run
    del st.session_state.query_to_run

with st.form("search_form", clear_on_submit=False):
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "Enter Dark Web Search Query",
        placeholder="e.g., ransomware payments, data breaches, zero-day exploits",
        label_visibility="collapsed",
        value=query_to_process if query_to_process else "",
        key="query_input",
    )
    run_button = col_button.form_submit_button("🔍 Run", use_container_width=True)

# Process the query
if (run_button and query) or query_to_process:
    start_time = time.time()
    
    # Validate query
    is_valid, error_msg = validate_query(query)
    if not is_valid:
        st.error(f"❌ Invalid query: {error_msg}")
        st.stop()
    
    # Add to history
    add_to_history(query)
    
    # Clear old state
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary", "all_iocs"]:
        st.session_state.pop(k, None)
    
    # Progress tracking
    progress_bar = st.progress(0)
    progress_text = st.empty()
    status_container = st.container()
    
    try:
        # Stage 1 - Load LLM (10%)
        with status_container:
            with st.status("🔄 Loading LLM...", expanded=False) as status:
                update_progress(progress_bar, progress_text, 0.1, "Loading LLM")
                llm = get_llm(model)
                status.update(label="✅ LLM Loaded", state="complete")
        
        # Stage 2 - Refine query (20%)
        with status_container:
            with st.status("🔄 Refining query...", expanded=False) as status:
                update_progress(progress_bar, progress_text, 0.2, "Refining Query")
                st.session_state.refined = refine_query(llm, query)
                status.update(label=f"✅ Query Refined: {st.session_state.refined[:50]}...", state="complete")
        
        # Display refined query
        cols = st.columns(3)
        with cols[0]:
            st.metric("Refined Query", st.session_state.refined[:30] + "..." if len(st.session_state.refined) > 30 else st.session_state.refined)
        
        # Stage 3 - Search dark web (+ optional Telegram) (40%)
        telegram_count = 0
        with status_container:
            with st.status("🔍 Searching dark web..." + (" + Telegram" if include_telegram else ""), expanded=False) as status:
                update_progress(progress_bar, progress_text, 0.4, "Searching Dark Web" + (" + Telegram" if include_telegram else ""))
                try:
                    st.session_state.results = get_search_results(
                        st.session_state.refined.replace(" ", "+"), 
                        max_workers=threads
                    )
                    if include_telegram and is_telegram_configured():
                        tg_results = get_telegram_results(st.session_state.refined, limit=50)
                        if tg_results:
                            seen_links = {r.get("link") for r in st.session_state.results if r.get("link")}
                            for r in tg_results:
                                link = r.get("link")
                                if link and link not in seen_links:
                                    seen_links.add(link)
                                    st.session_state.results.append(r)
                                    telegram_count += 1
                            status.update(label=f"✅ Found {len(st.session_state.results)} results (Telegram: {telegram_count})", state="complete")
                        else:
                            status.update(label=f"✅ Found {len(st.session_state.results)} results", state="complete")
                    else:
                        status.update(label=f"✅ Found {len(st.session_state.results)} results", state="complete")
                    if not st.session_state.results:
                        st.warning("⚠️ No results found. Try refining your query.")
                except Exception as e:
                    status.update(label=f"❌ Search failed: {str(e)}", state="error")
                    raise
        
        with cols[1]:
            st.metric("Search Results", len(st.session_state.results))
            if include_telegram and telegram_count:
                st.caption(f"Telegram: {telegram_count}")
        
        # Stage 4 - Filter results (60%)
        if st.session_state.results:
            with status_container:
                with st.status("🗂️ Filtering results...", expanded=False) as status:
                    update_progress(progress_bar, progress_text, 0.6, "Filtering Results")
                    try:
                        st.session_state.filtered = filter_results(
                            llm, st.session_state.refined, st.session_state.results
                        )
                        if not st.session_state.filtered:
                            st.warning("⚠️ No results passed filtering. Using top 10 results.")
                            st.session_state.filtered = st.session_state.results[:10]
                        status.update(label=f"✅ Filtered to {len(st.session_state.filtered)} results", state="complete")
                    except Exception as e:
                        st.warning(f"⚠️ Filtering failed: {str(e)}. Using all results.")
                        st.session_state.filtered = st.session_state.results[:20]
                        status.update(label=f"⚠️ Using {len(st.session_state.filtered)} results (filtering failed)", state="complete")
        else:
            st.session_state.filtered = []
            update_progress(progress_bar, progress_text, 0.6, "Skipping Filter (No Results)")
        
        with cols[2]:
            st.metric("Filtered Results", len(st.session_state.filtered))
        
        # Stage 5 - Scrape content (80%)
        if st.session_state.filtered:
            with status_container:
                with st.status("📜 Scraping content...", expanded=False) as status:
                    update_progress(progress_bar, progress_text, 0.8, "Scraping Content")
                    try:
                        st.session_state.scraped = scrape_multiple(
                            st.session_state.filtered, 
                            max_workers=threads
                        )
                        if not st.session_state.scraped:
                            st.warning("⚠️ Failed to scrape any content.")
                        status.update(label=f"✅ Scraped {len(st.session_state.scraped)} URLs", state="complete")
                    except Exception as e:
                        st.error(f"❌ Scraping failed: {str(e)}")
                        st.session_state.scraped = {}
                        status.update(label=f"❌ Scraping failed", state="error")
                        raise
        else:
            st.session_state.scraped = {}
            update_progress(progress_bar, progress_text, 0.8, "Skipping Scrape (No Results)")
        
        # Stage 6 - Extract IOCs (90%)
        st.session_state.all_iocs = {}
        if extract_iocs_flag:
            with status_container:
                with st.status("🔍 Extracting IOCs...", expanded=False) as status:
                    update_progress(progress_bar, progress_text, 0.9, "Extracting IOCs")
                    for url, content in st.session_state.scraped.items():
                        iocs = extract_iocs(content)
                        if iocs:
                            st.session_state.all_iocs = merge_iocs(st.session_state.all_iocs, iocs)
                    total_iocs = sum(len(v) for v in st.session_state.all_iocs.values())
                    status.update(label=f"✅ Extracted {total_iocs} IOCs", state="complete")
        
        # Stage 7 - Generate summary (100%)
        if st.session_state.scraped:
            st.session_state.streamed_summary = ""
            
            def ui_emit(chunk: str):
                st.session_state.streamed_summary += chunk
                summary_slot.markdown(st.session_state.streamed_summary)
            
            with status_container:
                with st.status("✍️ Generating summary...", expanded=False) as status:
                    update_progress(progress_bar, progress_text, 1.0, "Generating Summary")
                    summary_container = st.container()
                    with summary_container:
                        hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
                        with hdr_col:
                            st.subheader(":red[Investigation Summary]", anchor=None, divider="gray")
                        summary_slot = st.empty()
                    
                    try:
                        stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
                        llm.callbacks = [stream_handler]
                        _ = generate_summary(llm, query, st.session_state.scraped)
                        status.update(label="✅ Summary Generated", state="complete")
                    except Exception as e:
                        st.session_state.streamed_summary = f"# Investigation Summary\n\n**Query:** {query}\n\n**Error:** Failed to generate summary: {str(e)}\n\n**Results Found:** {len(st.session_state.results)}\n**Scraped URLs:** {len(st.session_state.scraped)}"
                        summary_slot.markdown(st.session_state.streamed_summary)
                        status.update(label=f"❌ Summary generation failed: {str(e)}", state="error")
                        st.error(f"Summary generation failed: {str(e)}")
        else:
            st.session_state.streamed_summary = f"# Investigation Summary\n\n**Query:** {query}\n\n**Status:** No content available to summarize.\n\n**Results Found:** {len(st.session_state.results) if st.session_state.results else 0}"
            summary_container = st.container()
            with summary_container:
                hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
                with hdr_col:
                    st.subheader(":red[Investigation Summary]", anchor=None, divider="gray")
                summary_slot = st.empty()
                summary_slot.markdown(st.session_state.streamed_summary)
            update_progress(progress_bar, progress_text, 1.0, "No Content to Summarize")
        
        # Calculate statistics
        query_time = time.time() - start_time
        ioc_count = sum(len(v) for v in st.session_state.all_iocs.values())
        update_statistics(query_time, ioc_count, len(st.session_state.results))
        
        # Display IOCs if extracted
        if extract_iocs_flag and st.session_state.all_iocs:
            st.divider()
            st.subheader("🔍 Extracted Indicators of Compromise (IOCs)")
            
            # IOC counts
            ioc_cols = st.columns(min(len(st.session_state.all_iocs), 5))
            for idx, (ioc_type, values) in enumerate(list(st.session_state.all_iocs.items())[:5]):
                with ioc_cols[idx]:
                    st.metric(ioc_type.upper(), len(values))
            
            # IOC tabs
            ioc_tabs = st.tabs(list(st.session_state.all_iocs.keys())[:10])
            for tab, (ioc_type, values) in zip(ioc_tabs, list(st.session_state.all_iocs.items())[:10]):
                with tab:
                    for value in sorted(values):
                        col1, col2 = st.columns([5, 1])
                        with col1:
                            st.code(value, language=None)
                        with col2:
                            st.button("📋", key=f"copy_{ioc_type}_{value}", help="Copy to clipboard")
            
            # Export IOCs
            st.subheader("Export IOCs")
            ioc_col1, ioc_col2, ioc_col3 = st.columns(3)
            with ioc_col1:
                ioc_json = format_iocs_for_export(st.session_state.all_iocs, format="json")
                st.download_button(
                    "Download IOCs (JSON)",
                    ioc_json,
                    file_name=f"iocs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            with ioc_col2:
                ioc_csv = format_iocs_for_export(st.session_state.all_iocs, format="csv")
                st.download_button(
                    "Download IOCs (CSV)",
                    ioc_csv,
                    file_name=f"iocs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            with ioc_col3:
                ioc_text = format_iocs_for_export(st.session_state.all_iocs, format="text")
                st.download_button(
                    "Download IOCs (Text)",
                    ioc_text,
                    file_name=f"iocs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
        
        # Result Preview
        if st.session_state.results:
            st.divider()
            st.subheader("📋 Search Results Preview")
            with st.expander(f"View {len(st.session_state.results)} Results", expanded=False):
                for idx, result in enumerate(st.session_state.results[:20]):
                    with st.expander(f"{idx + 1}. {result.get('title', 'No title')[:60]}..."):
                        st.write(f"**URL:** {result.get('link', 'N/A')}")
                        st.write(f"**Title:** {result.get('title', 'N/A')}")
                        if result.get('link') in st.session_state.scraped:
                            preview = st.session_state.scraped[result.get('link')][:200]
                            st.write(f"**Preview:** {preview}...")
        
        # Export Options
        st.divider()
        st.subheader("📥 Export Options")
        export_cols = st.columns(4)
        
        # Markdown export
        if export_format in ["Markdown", "All"]:
            with export_cols[0]:
                md_content = st.session_state.streamed_summary
                if extract_iocs_flag and st.session_state.all_iocs:
                    md_content += "\n\n## Extracted Indicators of Compromise (IOCs)\n\n"
                    md_content += format_iocs_for_export(st.session_state.all_iocs, format="text")
                st.download_button(
                    "📄 Download Markdown",
                    md_content,
                    file_name=f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
        
        # JSON export
        if export_format in ["JSON", "All"]:
            with export_cols[1]:
                json_data = {
                    "query": query,
                    "refined_query": st.session_state.refined,
                    "timestamp": datetime.now().isoformat(),
                    "summary": st.session_state.streamed_summary,
                    "source_urls": list(st.session_state.scraped.keys()),
                    "statistics": {
                        "total_search_results": len(st.session_state.results),
                        "filtered_results": len(st.session_state.filtered),
                        "scraped_urls": len(st.session_state.scraped),
                        "query_time_seconds": query_time
                    }
                }
                if extract_iocs_flag and st.session_state.all_iocs:
                    json_data["iocs"] = {k: list(v) for k, v in st.session_state.all_iocs.items()}
                    json_data["ioc_statistics"] = {k: len(v) for k, v in st.session_state.all_iocs.items()}
                
                st.download_button(
                    "📊 Download JSON",
                    json.dumps(json_data, indent=2, ensure_ascii=False),
                    file_name=f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
        # CSV export (for results)
        if export_format in ["CSV", "All"]:
            with export_cols[2]:
                csv_lines = ["URL,Title"]
                for result in st.session_state.results:
                    csv_lines.append(f'"{result.get("link", "")}","{result.get("title", "")}"')
                csv_content = "\n".join(csv_lines)
                st.download_button(
                    "📈 Download CSV",
                    csv_content,
                    file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Save query option
        with export_cols[3]:
            query_name = st.text_input("Save query as:", key="save_query_name", placeholder="Query name")
            if st.button("💾 Save Query") and query_name:
                st.session_state.saved_queries[query_name] = query
                st.success(f"Query '{query_name}' saved!")
                st.rerun()
        
        # Success message
        st.success(f"✅ Investigation complete! Processed in {query_time:.1f} seconds")
        
        # Clear progress
        progress_bar.empty()
        progress_text.empty()
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.info("💡 **Troubleshooting Tips:**\n"
                "- Check Tor connection\n"
                "- Verify LLM API keys\n"
                "- Try reducing thread count\n"
                "- Check network connectivity")
        progress_bar.empty()
        progress_text.empty()
        raise

# Footer
st.divider()
st.caption("Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/) | "
           "⚠️ Use responsibly and in compliance with applicable laws")
