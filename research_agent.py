# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "bedrock-agentcore-starter-toolkit>=0.1.28",
#   "boto3==1.40.69",
#   "mcp==1.25.0",
#   "nest-asyncio==1.6.0",
#   "python-dotenv==1.1.0",
#   "strands-agents==1.20.0",
# ]
# ///

from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from dotenv import load_dotenv


def load_research_agent_module():
    repo_root = Path(__file__).resolve().parent
    module_path = repo_root / "chapter5" / "research-agent" / "research_agent.py"
    spec = spec_from_file_location("chapter5_research_agent", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {module_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    module = load_research_agent_module()
    agent = module.ResearchAgent()
    today = date.today().strftime("%Y-%m-%d")
    agent.generate_report(today)


if __name__ == "__main__":
    main()
