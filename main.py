import click
import subprocess
import json
import os
from yaspin import yaspin
from datetime import datetime
from typing import Optional
from scrape import scrape_multiple
from search import get_search_results
from llm import get_llm, refine_query, filter_results, generate_summary
from people_utils import validate_person_input, normalize_person_input
from people_osint import run_people_investigation
from utils import (
    logger,
    validate_query,
    extract_iocs,
    format_iocs_for_export,
    merge_iocs,
    setup_logging,
    generate_pdf_report,
)


@click.group()
@click.version_option()
def robin():
    """Robin: AI-Powered Dark Web OSINT Tool."""
    pass


@robin.command()
@click.option(
    "--model",
    "-m",
    default="gpt4o",
    show_default=True,
    type=click.Choice(
        ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]
    ),
    help="Select LLM model to use (e.g., gpt4o, claude sonnet 3.5, ollama models)",
)
@click.option("--query", "-q", required=True, type=str, help="Dark web search query")
@click.option(
    "--threads",
    "-t",
    default=5,
    show_default=True,
    type=int,
    help="Number of threads to use for scraping (Default: 5)",
)
@click.option(
    "--output",
    "-o",
    type=str,
    help="Filename to save the final intelligence summary. If not provided, a filename based on the current date and time is used.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "json", "both", "pdf", "all"], case_sensitive=False),
    default="markdown",
    help="Output format: markdown, json, both, pdf, or all",
)
@click.option(
    "--extract-iocs",
    is_flag=True,
    default=False,
    help="Extract and export Indicators of Compromise (IOCs)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set logging level",
)
@click.option(
    "--log-file",
    type=str,
    default=None,
    help="Optional log file path",
)
@click.option(
    "--telegram",
    is_flag=True,
    default=False,
    help="Include Telegram OSINT search (public posts and joined chats). Requires TELEGRAM_* env vars.",
)
@click.option(
    "--rotate-circuit",
    is_flag=True,
    default=False,
    help="Enable Tor circuit rotation during scraping.",
)
@click.option(
    "--rotate-interval",
    type=int,
    default=None,
    help="Rotate Tor circuit after N requests (uses TOR_ROTATE_INTERVAL if not set).",
)
@click.option(
    "--skip-health-check",
    is_flag=True,
    default=False,
    help="Skip search engine health check for faster startup.",
)
@click.option(
    "--save-db",
    is_flag=True,
    default=False,
    help="Save investigation to SQLite database (~/.robin/robin.db).",
)
def cli(model, query, threads, output, format, extract_iocs, log_level, log_file, telegram, rotate_circuit, rotate_interval, skip_health_check, save_db):
    """Run Robin in CLI mode.\n
    Example commands:\n
    - robin -m gpt4o -q "ransomware payments" -t 12\n
    - robin --model claude-3-5-sonnet-latest --query "sensitive credentials exposure" --threads 8 --output filename\n
    - robin -m llama3.1 -q "zero days" --extract-iocs --format json\n
    """
    # Setup logging
    setup_logging(log_level=log_level, log_file=log_file)
    logger.info(f"Starting Robin investigation with model: {model}, query: {query[:100]}...")
    
    # Validate query
    is_valid, error_msg = validate_query(query)
    if not is_valid:
        click.echo(f"[ERROR] Invalid query: {error_msg}", err=True)
        raise click.Abort()
    
    try:
        llm = get_llm(model)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        click.echo(f"[ERROR] Failed to initialize LLM: {e}", err=True)
        raise click.Abort()

    # Show spinner while processing the query
    with yaspin(text="Processing...", color="cyan") as sp:
        try:
            refined_query = refine_query(llm, query)
        except Exception as e:
            logger.error(f"Error refining query: {e}")
            click.echo(f"[ERROR] Failed to refine query: {e}", err=True)
            raise click.Abort()

        try:
            search_results = get_search_results(
                refined_query.replace(" ", "+"),
                max_workers=threads,
                include_telegram=telegram,
                skip_health_check=skip_health_check,
            )
        except Exception as e:
            logger.error(f"Error getting search results: {e}")
            click.echo(f"[ERROR] Failed to get search results: {e}", err=True)
            raise click.Abort()

        try:
            search_filtered = filter_results(llm, refined_query, search_results)
        except Exception as e:
            logger.error(f"Error filtering results: {e}")
            click.echo(f"[WARNING] Error filtering results, using all results: {e}", err=True)
            search_filtered = search_results[:20]  # Fallback to top 20

        try:
            scraped_results = scrape_multiple(
                search_filtered,
                max_workers=threads,
                rotate=rotate_circuit,
                rotate_interval=rotate_interval if rotate_circuit else None,
            )
        except Exception as e:
            logger.error(f"Error scraping results: {e}")
            click.echo(f"[ERROR] Failed to scrape results: {e}", err=True)
            raise click.Abort()
        
        sp.ok("✔")

    # Extract IOCs if requested
    all_iocs = {}
    if extract_iocs:
        logger.info("Extracting IOCs from scraped content...")
        with yaspin(text="Extracting IOCs...", color="yellow") as sp_ioc:
            for url, content in scraped_results.items():
                iocs = extract_iocs(content)
                if iocs:
                    all_iocs = merge_iocs(all_iocs, iocs)
            sp_ioc.ok("✔")
        
        if all_iocs:
            total_iocs = sum(len(v) for v in all_iocs.values())
            logger.info(f"Extracted {total_iocs} IOCs across {len(all_iocs)} types")
            click.echo(f"\n[IOCs] Extracted {total_iocs} indicators of compromise")

    # Generate the intelligence summary
    try:
        with yaspin(text="Generating summary...", color="green") as sp_sum:
            summary = generate_summary(llm, query, scraped_results)
            sp_sum.ok("✔")
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        click.echo(f"[ERROR] Failed to generate summary: {e}", err=True)
        raise click.Abort()

    # Determine output filename
    if not output:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_filename = f"summary_{now}"
    else:
        base_filename = output

    # Save outputs
    files_created = []
    
    if format.lower() in ["markdown", "both", "all"]:
        filename = f"{base_filename}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)
            if extract_iocs and all_iocs:
                f.write("\n\n## Extracted Indicators of Compromise (IOCs)\n\n")
                f.write(format_iocs_for_export(all_iocs, format="text"))
        files_created.append(filename)
        click.echo(f"\n[OUTPUT] Markdown summary saved to {filename}")
    
    if format.lower() in ["json", "both", "all"]:
        filename = f"{base_filename}.json"
        output_data = {
            "query": query,
            "refined_query": refined_query,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "source_urls": list(scraped_results.keys()),
            "statistics": {
                "total_search_results": len(search_results),
                "filtered_results": len(search_filtered),
                "scraped_urls": len(scraped_results),
            }
        }
        
        if extract_iocs and all_iocs:
            output_data["iocs"] = {k: list(v) for k, v in all_iocs.items()}
            output_data["ioc_statistics"] = {
                k: len(v) for k, v in all_iocs.items()
            }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        files_created.append(filename)
        click.echo(f"[OUTPUT] JSON summary saved to {filename}")
    
    # Save IOCs separately if extracted
    if extract_iocs and all_iocs:
        ioc_filename = f"{base_filename}_iocs.json"
        with open(ioc_filename, "w", encoding="utf-8") as f:
            json.dump({k: list(v) for k, v in all_iocs.items()}, f, indent=2)
        files_created.append(ioc_filename)
        
        ioc_csv_filename = f"{base_filename}_iocs.csv"
        with open(ioc_csv_filename, "w", encoding="utf-8") as f:
            f.write(format_iocs_for_export(all_iocs, format="csv"))
        files_created.append(ioc_csv_filename)
        
        ioc_stix_filename = f"{base_filename}_iocs.stix.json"
        with open(ioc_stix_filename, "w", encoding="utf-8") as f:
            f.write(format_iocs_for_export(all_iocs, format="stix"))
        files_created.append(ioc_stix_filename)
        
        ioc_misp_filename = f"{base_filename}_iocs.misp.json"
        with open(ioc_misp_filename, "w", encoding="utf-8") as f:
            f.write(format_iocs_for_export(all_iocs, format="misp"))
        files_created.append(ioc_misp_filename)
        
        click.echo(f"[OUTPUT] IOCs saved to {ioc_filename}, {ioc_csv_filename}, {ioc_stix_filename}, {ioc_misp_filename}")
    
    if format.lower() in ["pdf", "all"]:
        pdf_filename = f"{base_filename}.pdf"
        if generate_pdf_report(summary, pdf_filename, all_iocs if extract_iocs else None):
            files_created.append(pdf_filename)
            click.echo(f"[OUTPUT] PDF report saved to {pdf_filename}")
        else:
            click.echo("[WARNING] PDF generation failed. Install reportlab.", err=True)
    
    if save_db:
        try:
            from db import get_connection, save_investigation
            from config import ROBIN_DB_PATH
            conn = get_connection(ROBIN_DB_PATH or None)
            inv_id = save_investigation(
                conn,
                query=query,
                refined_query=refined_query,
                summary=summary,
                search_results=search_results,
                scraped_urls=list(scraped_results.keys()),
                iocs=all_iocs if extract_iocs else None,
            )
            conn.close()
            click.echo(f"[OUTPUT] Saved to database (investigation ID: {inv_id})")
        except Exception as e:
            logger.error(f"Database save failed: {e}")
            click.echo(f"[WARNING] Database save failed: {e}", err=True)
    
    click.echo(f"\n[SUCCESS] Investigation complete! Created {len(files_created)} file(s)")


def _run_single_investigation(llm, query, threads, extract_iocs_flag, rotate_circuit, rotate_interval, skip_health_check, telegram):
    """Run a single investigation and return (refined_query, search_results, filtered, scraped, summary, all_iocs)."""
    refined_query = refine_query(llm, query)
    search_results = get_search_results(
        refined_query.replace(" ", "+"),
        max_workers=threads,
        include_telegram=telegram,
        skip_health_check=skip_health_check,
    )
    search_filtered = filter_results(llm, refined_query, search_results)
    if not search_filtered:
        search_filtered = search_results[:20]
    scraped_results = scrape_multiple(
        search_filtered,
        max_workers=threads,
        rotate=rotate_circuit,
        rotate_interval=rotate_interval if rotate_circuit else None,
    )
    all_iocs = {}
    if extract_iocs_flag:
        for url, content in scraped_results.items():
            iocs = extract_iocs(content)
            if iocs:
                all_iocs = merge_iocs(all_iocs, iocs)
    summary = generate_summary(llm, query, scraped_results)
    return refined_query, search_results, search_filtered, scraped_results, summary, all_iocs


@robin.command("batch")
@click.option("--batch", "-b", "batch_file", required=True, type=click.Path(exists=True), help="File with one query per line")
@click.option("--model", "-m", default="gpt4o", type=click.Choice(["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]))
@click.option("--threads", "-t", default=5, type=int)
@click.option("--output", "-o", type=str, help="Output filename base for batch report")
@click.option("--format", "-f", type=click.Choice(["markdown", "json", "both", "pdf", "all"]), default="markdown")
@click.option("--extract-iocs", is_flag=True, default=False)
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO")
@click.option("--log-file", type=str, default=None)
@click.option("--telegram", is_flag=True, default=False)
@click.option("--rotate-circuit", is_flag=True, default=False)
@click.option("--rotate-interval", type=int, default=None)
@click.option("--skip-health-check", is_flag=True, default=False)
def batch_cmd(batch_file, model, threads, output, format, extract_iocs, log_level, log_file, telegram, rotate_circuit, rotate_interval, skip_health_check):
    """Run batch investigation from a file with one query per line."""
    setup_logging(log_level=log_level, log_file=log_file)
    
    with open(batch_file, "r", encoding="utf-8") as f:
        queries = [q.strip() for q in f if q.strip()]
    if not queries:
        click.echo("[ERROR] No queries found in batch file", err=True)
        raise click.Abort()
    
    logger.info(f"Batch mode: {len(queries)} queries from {batch_file}")
    click.echo(f"\n[BATCH] Processing {len(queries)} queries...\n")
    
    try:
        llm = get_llm(model)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        click.echo(f"[ERROR] Failed to initialize LLM: {e}", err=True)
        raise click.Abort()
    
    results_list = []
    merged_iocs = {}
    
    for idx, query in enumerate(queries):
        is_valid, error_msg = validate_query(query)
        if not is_valid:
            click.echo(f"[WARN] Skipping invalid query {idx + 1}: {error_msg}")
            continue
        click.echo(f"  [{idx + 1}/{len(queries)}] {query[:60]}...")
        with yaspin(text="Processing...", color="cyan") as sp:
            try:
                refined, search_res, filtered, scraped, summary, iocs = _run_single_investigation(
                    llm, query, threads, extract_iocs, rotate_circuit, rotate_interval,
                    skip_health_check, telegram
                )
                results_list.append({
                    "query": query,
                    "refined_query": refined,
                    "search_results": len(search_res),
                    "filtered": len(filtered),
                    "scraped": len(scraped),
                    "summary": summary,
                    "iocs": iocs,
                })
                merged_iocs = merge_iocs(merged_iocs, iocs)
                sp.ok("✔")
            except Exception as e:
                logger.error(f"Batch query failed: {e}")
                sp.fail("✗")
                click.echo(f"    [ERROR] {e}")
    
    if not results_list:
        click.echo("[ERROR] No successful investigations", err=True)
        raise click.Abort()
    
    base = output or f"batch_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    files_created = []
    
    combined_md = "# Batch Investigation Report\n\n"
    for r in results_list:
        combined_md += f"## Query: {r['query']}\n\n"
        combined_md += f"**Refined:** {r['refined_query']}\n\n"
        combined_md += f"**Results:** {r['search_results']} search, {r['filtered']} filtered, {r['scraped']} scraped\n\n"
        combined_md += r["summary"] + "\n\n---\n\n"
    
    if extract_iocs and merged_iocs:
        combined_md += "\n## Aggregated IOCs\n\n"
        combined_md += format_iocs_for_export(merged_iocs, format="text")
    
    if format.lower() in ["markdown", "both", "all"]:
        fn = f"{base}.md"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(combined_md)
        files_created.append(fn)
        click.echo(f"\n[OUTPUT] Markdown: {fn}")
    
    if format.lower() in ["json", "both", "all"]:
        fn = f"{base}.json"
        data = {
            "batch_file": batch_file,
            "timestamp": datetime.now().isoformat(),
            "queries_count": len(results_list),
            "investigations": [
                {
                    "query": r["query"],
                    "refined_query": r["refined_query"],
                    "search_results": r["search_results"],
                    "filtered": r["filtered"],
                    "scraped": r["scraped"],
                    "summary": r["summary"],
                    "iocs": {k: list(v) for k, v in r["iocs"].items()} if r["iocs"] else {},
                }
                for r in results_list
            ],
            "aggregated_iocs": {k: list(v) for k, v in merged_iocs.items()} if merged_iocs else {},
        }
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        files_created.append(fn)
        click.echo(f"[OUTPUT] JSON: {fn}")
    
    if format.lower() in ["pdf", "all"]:
        fn = f"{base}.pdf"
        if generate_pdf_report(combined_md, fn, merged_iocs if extract_iocs else None):
            files_created.append(fn)
            click.echo(f"[OUTPUT] PDF: {fn}")
    
    if extract_iocs and merged_iocs:
        ioc_fn = f"{base}_iocs.json"
        with open(ioc_fn, "w", encoding="utf-8") as f:
            json.dump({k: list(v) for k, v in merged_iocs.items()}, f, indent=2)
        files_created.append(ioc_fn)
    
    click.echo(f"\n[SUCCESS] Batch complete. Created {len(files_created)} file(s)")


@robin.command("people")
@click.option("--name", "-n", type=str, default=None, help="Person name")
@click.option("--email", "-e", type=str, default=None, help="Email address (comma-separated for multiple)")
@click.option("--username", "-u", type=str, default=None, help="Username (comma-separated for multiple)")
@click.option("--phone", "-p", type=str, default=None, help="Phone number (comma-separated for multiple)")
@click.option("--model", "-m", default="gpt4o", type=click.Choice(["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"]))
@click.option("--threads", "-t", default=5, type=int)
@click.option("--output", "-o", type=str, help="Filename base for report")
@click.option("--format", "-f", type=click.Choice(["markdown", "json", "both", "pdf", "all"], case_sensitive=False), default="markdown")
@click.option("--extract-iocs", is_flag=True, default=False)
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]), default="INFO")
@click.option("--log-file", type=str, default=None)
@click.option("--telegram", is_flag=True, default=False)
@click.option("--rotate-circuit", is_flag=True, default=False)
@click.option("--rotate-interval", type=int, default=None)
@click.option("--skip-health-check", is_flag=True, default=False)
@click.option("--save-db", is_flag=True, default=False)
def people_cmd(name, email, username, phone, model, threads, output, format, extract_iocs, log_level, log_file, telegram, rotate_circuit, rotate_interval, skip_health_check, save_db):
    """Run People Search (OSINT): at least one of --name, --email, --username, --phone required."""
    setup_logging(log_level=log_level, log_file=log_file)
    is_valid, err = validate_person_input(name=name, email=email, username=username, phone=phone)
    if not is_valid:
        click.echo(f"[ERROR] {err}", err=True)
        raise click.Abort()
    person_input = normalize_person_input(name=name, email=email, username=username, phone=phone)
    try:
        llm = get_llm(model)
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        click.echo(f"[ERROR] Failed to initialize LLM: {e}", err=True)
        raise click.Abort()
    with yaspin(text="People investigation...", color="cyan") as sp:
        try:
            person_input, profile, search_results, scraped_results, summary, all_iocs = run_people_investigation(
                llm,
                person_input,
                threads=threads,
                extract_iocs_flag=extract_iocs,
                include_telegram=telegram,
                include_clear_web=True,
                skip_health_check=skip_health_check,
                rotate_circuit=rotate_circuit,
                rotate_interval=rotate_interval,
            )
            sp.ok("✔")
        except Exception as e:
            logger.error(f"People investigation failed: {e}")
            sp.fail("✗")
            click.echo(f"[ERROR] {e}", err=True)
            raise click.Abort()
    base_filename = output or f"people_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    files_created = []
    profile_md = _format_profile_md(profile)
    full_md = f"# People Investigation Report\n\n{profile_md}\n\n## Investigation Summary\n\n{summary}"
    if extract_iocs and all_iocs:
        full_md += "\n\n## IOCs Linked to This Person\n\n"
        full_md += format_iocs_for_export(all_iocs, format="text")
    if format.lower() in ["markdown", "both", "all"]:
        fn = f"{base_filename}.md"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(full_md)
        files_created.append(fn)
        click.echo(f"\n[OUTPUT] Markdown: {fn}")
    if format.lower() in ["json", "both", "all"]:
        fn = f"{base_filename}.json"
        def _serialize_profile_value(v):
            if isinstance(v, (list, set)):
                return list(v)
            if isinstance(v, dict) and v and isinstance(next(iter(v.values()), None), (set, list)):
                return {kk: list(vv) if isinstance(vv, (list, set)) else vv for kk, vv in v.items()}
            return v
        out_data = {
            "person_input": person_input,
            "person_profile": {k: _serialize_profile_value(v) for k, v in profile.items()},
            "summary": summary,
            "source_urls": list(scraped_results.keys()),
            "statistics": {"search_results": len(search_results), "scraped": len(scraped_results)},
        }
        if extract_iocs and all_iocs:
            out_data["iocs"] = {k: list(v) for k, v in all_iocs.items()}
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2, ensure_ascii=False)
        files_created.append(fn)
        click.echo(f"[OUTPUT] JSON: {fn}")
    if format.lower() in ["pdf", "all"]:
        pdf_fn = f"{base_filename}.pdf"
        if generate_pdf_report(full_md, pdf_fn, all_iocs if extract_iocs else None):
            files_created.append(pdf_fn)
            click.echo(f"[OUTPUT] PDF: {pdf_fn}")
    if extract_iocs and all_iocs:
        ioc_fn = f"{base_filename}_iocs.json"
        with open(ioc_fn, "w", encoding="utf-8") as f:
            json.dump({k: list(v) for k, v in all_iocs.items()}, f, indent=2)
        files_created.append(ioc_fn)
    if save_db:
        try:
            from db import get_connection, save_investigation
            from config import ROBIN_DB_PATH
            conn = get_connection(ROBIN_DB_PATH or None)
            inv_id = save_investigation(
                conn,
                query=f"people:{person_input.get('name') or person_input.get('emails') or person_input.get('usernames') or 'unknown'}",
                refined_query="",
                summary=summary,
                search_results=search_results,
                scraped_urls=list(scraped_results.keys()),
                iocs=all_iocs if extract_iocs else None,
            )
            conn.close()
            click.echo(f"[OUTPUT] Saved to database (investigation ID: {inv_id})")
        except Exception as e:
            logger.error(f"Database save failed: {e}")
            click.echo(f"[WARNING] Database save failed: {e}", err=True)
    click.echo(f"\n[SUCCESS] People investigation complete. Created {len(files_created)} file(s)")


def _format_profile_md(profile):
    """Format person profile dict as markdown section."""
    lines = ["## Person Profile\n"]
    if profile.get("name"):
        lines.append(f"- **Name:** {profile['name']}")
    if profile.get("emails"):
        lines.append(f"- **Emails:** {', '.join(profile['emails'])}")
    if profile.get("usernames"):
        lines.append(f"- **Usernames:** {', '.join(profile['usernames'])}")
    if profile.get("phones"):
        lines.append(f"- **Phones:** {', '.join(profile['phones'])}")
    if profile.get("social_links"):
        lines.append(f"- **Social links:** {', '.join(profile['social_links'][:20])}")
    if profile.get("dark_web_mentions"):
        lines.append(f"- **Dark/clear web mentions:** {len(profile['dark_web_mentions'])} URL(s)")
    if profile.get("api_snippets"):
        lines.append("- **API snippets:**")
        for s in profile["api_snippets"][:15]:
            lines.append(f"  - {s}")
    return "\n".join(lines)


@robin.command("api")
@click.option("--host", default="0.0.0.0", help="API host")
@click.option("--port", "-p", default=8000, type=int, help="API port")
def api_cmd(host, port):
    """Run Robin REST API server."""
    from api import run_api
    run_api(host=host, port=port)


@robin.command()
@click.option(
    "--ui-port",
    default=8501,
    show_default=True,
    type=int,
    help="Port for the Streamlit UI",
)
@click.option(
    "--ui-host",
    default="localhost",
    show_default=True,
    type=str,
    help="Host for the Streamlit UI",
)
def ui(ui_port, ui_host):
    """Run Robin in Web UI mode."""
    import sys, os

    # Use streamlit's internet CLI entrypoint
    from streamlit.web import cli as stcli

    # When PyInstaller one-file, data files livei n _MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)

    ui_script = os.path.join(base, "ui.py")
    # Build sys.argv
    sys.argv = [
        "streamlit",
        "run",
        ui_script,
        f"--server.port={ui_port}",
        f"--server.address={ui_host}",
        "--global.developmentMode=false",
    ]
    # This will never return until streamlit exits
    sys.exit(stcli.main())


if __name__ == "__main__":
    robin()
