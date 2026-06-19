import asyncio
from app.agent import root_agent

async def main():
    apps_to_build = [
        "1. Ciao! Voglio costruire una web app Next.js per la generazione di immagini AI con UI dark mode e glassmorphism.",
        "2. Puoi sviluppare un backend Python FastAPI per un'app di ricerca semantica usando pgvector?",
        "3. Sviluppa una dashboard web in React che mostra le metriche degli agenti AI e l'uso dei token in tempo reale."
    ]

    for idx, prompt in enumerate(apps_to_build):
        print(f"\n--- Test Case {idx + 1} ---")
        print(f"User Request: '{prompt}'")
        try:
            print(f"Agent Orchestrator Response:")
            async for chunk in root_agent.run_async(prompt):
                if hasattr(chunk, 'text'):
                    print(chunk.text, end="")
            print("\n")
        except Exception as e:
            import traceback
            print(f"Error: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
