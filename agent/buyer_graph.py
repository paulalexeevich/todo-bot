from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent.nodes.buyer import buyer_node
from db.models import Offer


class BuyerState(TypedDict):
    task_text: str
    search_query: str
    location_type: str      # local | online | any
    current_location: str   # e.g. "Amsterdam, Netherlands"
    home_location: str      # e.g. "Moscow, Russia"
    offers: list[Offer]


def build_buyer_graph():
    graph = StateGraph(BuyerState)
    graph.add_node("buyer", buyer_node)
    graph.add_edge(START, "buyer")
    graph.add_edge("buyer", END)
    return graph.compile()


buyer_graph = build_buyer_graph()
