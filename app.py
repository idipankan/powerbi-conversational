import os
import json
import requests
import streamlit as st
from msal import ConfidentialClientApplication
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()

PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
WORKSPACES_FILE = "workspaces.json"   
CONTEXT_FILE    = "context.txt"       

class PBIAuth:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}"
        )

    def get_token(self) -> str:
        result = self.app.acquire_token_for_client(
            scopes=["https://analysis.windows.net/powerbi/api/.default"]
        )
        if "access_token" in result:
            return result["access_token"]
        raise Exception(f"Power BI auth failed: {result.get('error_description')}")

@st.cache_data(ttl=3600)
def load_workspaces() -> Dict[str, Dict[str, str]]:
    """Load the workspace → IDs mapping from JSON."""
    with open(WORKSPACES_FILE, "r") as f:
        return json.load(f)

@st.cache_data(ttl=3600)
def load_system_context() -> str:
    """Read the static context for the Usage Metrics data model."""
    with open(CONTEXT_FILE, "r") as f:
        return f.read()

class DAXGenerator:
    def __init__(self, openai_key: str, system_context: str):
        self.llm = OpenAI(api_key=openai_key)
        self.system_context = system_context

    def generate(self, metadata: Dict[str, Any], question: str) -> str:
        """
        Prompt structure:
          - system: the static context (tables, measures, relationships)
          - user: describes the question and dataset metadata
        """
        system_msg = {
            "role": "system",
            "content": self.system_context
        }
        user_msg = {
            "role": "user",
            "content": (
                "You have this dataset metadata:\n"
                f"{json.dumps(metadata)}\n\n"
                f"Generate a DAX query to answer: {question}\n"
                "Remove any special formatting, if any. Return only the DAX code."
            )
        }
        resp = self.llm.chat.completions.create(
            model="gpt-4.1",
            messages=[system_msg, user_msg]
        )
        return resp.choices[0].message.content.strip()

class PBIQuery:
    def __init__(self, token: str, workspace_id: str, dataset_id: str):
        self.token = token
        self.workspace_id = workspace_id
        self.dataset_id = dataset_id

    def execute(self, dax: str) -> Dict[str, Any]:
        url = (
            f"{PBI_API_BASE}/groups/{self.workspace_id}"
            f"/datasets/{self.dataset_id}/executeQueries"
        )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        body = {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}}
        resp = requests.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()

class ResponseParser:
    def __init__(self, openai_key: str, system_context: str):
        self.llm = OpenAI(api_key=openai_key)
        self.system_context = system_context

    def parse(self, raw_json: Dict[str, Any], question: str) -> str:
        """
        Use the same system context plus the original question to
        translate the raw JSON results into a coherent narrative.
        """
        system_msg = {
            "role": "system",
            "content": self.system_context
        }
        user_msg = {
            "role": "user",
            "content": (
                "Here are the raw results of a DAX query for usage stats:\n"
                f"{json.dumps(raw_json, indent=2)}\n\n"
                f"Explain these results in plain English to answer: {question}"
            )
        }
        resp = self.llm.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[system_msg, user_msg]
        )
        return resp.choices[0].message.content.strip()

def main():
    st.title("Report Usage Insights")

    # Sidebar config
    tenant_id     = os.getenv("AZURE_TENANT_ID", "")
    client_id     = os.getenv("AZURE_CLIENT_ID", "")
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
    openai_key    = os.getenv("OPENAI_API_KEY", "")
    max_retries   = st.sidebar.number_input("Max DAX retries", min_value=1, value=3)

    # Load lookups & context
    workspaces     = load_workspaces()
    system_context = load_system_context()

    # Workspace selector
    choice = st.selectbox("Report Workspace", list(workspaces.keys()))
    ws_info = workspaces[choice]
    st.write(f"Selected workspace `{choice}`: ID={ws_info['workspace_id']}")

    # User question
    question = st.text_input("Describe your requirement")

    if st.button("Run"):
        # 1. Authenticate
        with st.spinner("Authenticating to Power BI…"):
            token = PBIAuth(tenant_id, client_id, client_secret).get_token()
            st.success("Authenticated")

        metadata = {
            "workspace_id": ws_info["workspace_id"],
            "dataset_id":   ws_info["dataset_id"],
        }

        dax_gen = DAXGenerator(openai_key, system_context)
        executor = PBIQuery(token, ws_info["workspace_id"], ws_info["dataset_id"])
        raw_json = None

        for attempt in range(1, max_retries + 1):
            with st.spinner(f"[{attempt}/{max_retries}] Generating DAX…"):
                dax = dax_gen.generate(metadata, question)
                st.code(dax, language="dax")
            with st.spinner("Executing DAX…"):
                try:
                    raw_json = executor.execute(dax)
                    st.success("Query succeeded")
                    break
                except Exception as e:
                    st.error(f"Exec failed: {e}")
                    if attempt == max_retries:
                        st.warning("All retry attempts failed. Please refine your question.")
                        break
                    st.info("Retrying…")

        parser = ResponseParser(openai_key, system_context)
        with st.spinner("Parsing results…"):
            answer = parser.parse(raw_json, question)
        st.subheader("Insight")
        st.write(answer)


if __name__ == "__main__":
    main()
