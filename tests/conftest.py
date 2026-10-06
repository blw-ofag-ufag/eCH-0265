from pathlib import Path
import pytest
from rdflib import Graph

# Tests that produce human-readable reports write them to this directory.
TEST_LOG_DIR = Path("build/test")

def pytest_addoption(parser):
    parser.addoption(
        "--template-ref",
        action="store",
        default="latest",
        help="Tag (e.g., 'v1.2.3') or 'latest' of the template repository to check against."
    )

@pytest.fixture(scope="session", autouse=True)
def clear_test_logs():
    """Removes the reports of the previous test run, so that every report in
    build/test belongs to the current run (GitHub issue #40)."""
    if TEST_LOG_DIR.is_dir():
        for log in TEST_LOG_DIR.glob("*.log"):
            log.unlink()


@pytest.fixture(scope="session")
def final_graph():
    """Loads the fully reasoned and processed graph for testing."""
    g = Graph()
    g.parse("build/rdf/03-processed.ttl", format="turtle")
    return g