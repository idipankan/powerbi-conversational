# Report Usage Insights

This Streamlit app provides a natural language interface to obtain insights from Power BI Usage Metrics datasets. Users can ask questions in plain English, and the app will generate, execute, and interpret DAX queries to deliver actionable insights.

## Architecture

![Architecture](https://idipankan.com/wp-content/uploads/2025/06/Natural-Language-OLAP-LLM.drawio.png)

## How It Works

The process for obtaining insights involves several key steps:

1. **Authentication**
   - The app authenticates to the Power BI REST API using Azure AD credentials (Tenant ID, Client ID, Client Secret) via the Microsoft Authentication Library (MSAL).
   - An access token is obtained for secure API calls.

2. **Workspace and Context Loading**
   - The app loads available Power BI workspaces and their IDs from a local `workspaces.json` file.
   - It also loads a static context description (tables, measures, relationships) from `context.txt` to inform the language model.

3. **User Input**
   - The user selects a workspace and enters a question describing their reporting requirement.

4. **DAX Query Generation**
   - The app uses OpenAI's GPT model to generate a DAX query based on the user's question and the dataset metadata.
   - The prompt includes both the static context and the user's question.

5. **Query Execution**
   - The generated DAX query is executed against the selected Power BI dataset using the Power BI REST API.
   - The app handles retries in case of execution failures.

6. **Result Parsing and Explanation**
   - The raw JSON results from the DAX query are sent to the language model, along with the original question and context.
   - The model translates the results into a plain English explanation, providing actionable insights.

## Files
- `app.py`: Main application logic.
- `workspaces.json`: Mapping of workspace names to their IDs and dataset IDs.
- `context.txt`: Static context for the Usage Metrics data model.

## Requirements
- Python 3.8+
- Streamlit
- msal
- openai
- requests
- python-dotenv

## Usage
1. Set up your Azure and OpenAI credentials in a `.env` file:
   ```env
   AZURE_TENANT_ID=your-tenant-id
   AZURE_CLIENT_ID=your-client-id
   AZURE_CLIENT_SECRET=your-client-secret
   OPENAI_API_KEY=your-openai-key
   ```
2. Add your workspace and dataset info to `workspaces.json`.
3. Run the app:
   ```bash
   streamlit run app.py
   ```
4. Interact with the app in your browser. 
