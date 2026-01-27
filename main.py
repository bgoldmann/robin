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
from utils import (
    logger,
    validate_query,
    extract_iocs,
    format_iocs_for_export,
    merge_iocs,
    setup_logging
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
    type=click.Choice(["markdown", "json", "both"], case_sensitive=False),
    default="markdown",
    help="Output format: markdown, json, or both",
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
def cli(model, query, threads, output, format, extract_iocs, log_level, log_file):
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
                refined_query.replace(" ", "+"), max_workers=threads
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
            scraped_results = scrape_multiple(search_filtered, max_workers=threads)
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
    
    if format.lower() in ["markdown", "both"]:
        filename = f"{base_filename}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(summary)
            if extract_iocs and all_iocs:
                f.write("\n\n## Extracted Indicators of Compromise (IOCs)\n\n")
                f.write(format_iocs_for_export(all_iocs, format="text"))
        files_created.append(filename)
        click.echo(f"\n[OUTPUT] Markdown summary saved to {filename}")
    
    if format.lower() in ["json", "both"]:
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
        
        # Also save as CSV
        ioc_csv_filename = f"{base_filename}_iocs.csv"
        with open(ioc_csv_filename, "w", encoding="utf-8") as f:
            f.write(format_iocs_for_export(all_iocs, format="csv"))
        files_created.append(ioc_csv_filename)
        click.echo(f"[OUTPUT] IOCs saved to {ioc_filename} and {ioc_csv_filename}")
    
    click.echo(f"\n[SUCCESS] Investigation complete! Created {len(files_created)} file(s)")


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
