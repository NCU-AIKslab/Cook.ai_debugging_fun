from langgraph.graph import StateGraph, END
from .state import SummarizationState
from .nodes import retrieve_chunks_node, summarize_node

# Define the graph
builder = StateGraph(SummarizationState)

# Add the nodes
builder.add_node("retrieve_chunks", retrieve_chunks_node)
builder.add_node("summarize", summarize_node)

# Set the entry point
builder.set_entry_point("retrieve_chunks")

# Define the edges
builder.add_edge("retrieve_chunks", "summarize")
builder.add_edge("summarize", END)

# Compile the graph
app = builder.compile()
