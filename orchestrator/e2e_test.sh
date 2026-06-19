#!/bin/bash

# Start the ADK local playground server in the background for faster iterations
echo "Starting local server..."
uvx google-agents-cli run --start-server "Ping" > /dev/null 2>&1

PROMPTS=(
    "1. Ciao! Voglio costruire una web app Next.js per la generazione di immagini AI con UI dark mode e glassmorphism. Usa delegate_dev_task per delegare il lavoro allo sviluppatore."
    "2. Puoi sviluppare un backend Python FastAPI per un'app di ricerca semantica usando pgvector? Usa delegate_dev_task per delegare il lavoro allo sviluppatore."
    "3. Sviluppa una dashboard web in React che mostra le metriche degli agenti AI e l'uso dei token in tempo reale. Usa delegate_dev_task per delegare il lavoro allo sviluppatore."
)

for i in "${!PROMPTS[@]}"; do
    echo "========================================"
    echo "Test Case $((i+1))"
    echo "User Request: ${PROMPTS[$i]}"
    echo "----------------------------------------"
    echo "Agent Orchestrator Response:"
    uvx google-agents-cli run "${PROMPTS[$i]}"
    echo "========================================"
    echo ""
    sleep 2
done

# Stop the server
uvx google-agents-cli run --stop-server > /dev/null 2>&1
echo "Tests completed."
