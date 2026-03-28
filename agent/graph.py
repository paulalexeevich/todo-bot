from langgraph.graph import END, START, StateGraph

from agent.nodes.hackernews import hackernews_node
from agent.nodes.indiehackers import indiehackers_node
from agent.nodes.producthunt import producthunt_node
from agent.nodes.reddit import reddit_node
from agent.nodes.synthesize import synthesize_node
from agent.state import DiscoveryState


def build_graph():
    graph = StateGraph(DiscoveryState)

    graph.add_node("reddit", reddit_node)
    graph.add_node("hackernews", hackernews_node)
    graph.add_node("producthunt", producthunt_node)
    graph.add_node("indiehackers", indiehackers_node)
    graph.add_node("synthesize", synthesize_node)

    # All research nodes run in parallel from START
    graph.add_edge(START, "reddit")
    graph.add_edge(START, "hackernews")
    graph.add_edge(START, "producthunt")
    graph.add_edge(START, "indiehackers")

    # All research nodes feed into synthesize
    graph.add_edge("reddit", "synthesize")
    graph.add_edge("hackernews", "synthesize")
    graph.add_edge("producthunt", "synthesize")
    graph.add_edge("indiehackers", "synthesize")

    graph.add_edge("synthesize", END)

    return graph.compile()


# Compiled once at import time, reused across runs
discovery_graph = build_graph()
