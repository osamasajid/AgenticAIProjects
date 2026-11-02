"""Mock connectors (Wave C).

Every connector is a MOCK now with a clean interface, selected by env
(e.g. GOOGLE_OAUTH=mock|real). A real implementation can be swapped in later
without touching the LangGraph agent, the Tool Layer, or the UI. Each connector
ships a conformance-style test.
"""
