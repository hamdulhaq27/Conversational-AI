# Natural Language Processing - Assignment 2
## Conversational AI System: Restaurant Reservation Assistant

**Group Members:**
1. Mohammad Haider Abbas (23i-2558)
2. Hamdul Haq (23i-0081)
3. Ayesha Ikram (23i-0109)

## 📖 Overview
This repository contains a fully local, CPU-optimized, microservices-based conversational AI system that acts as a restaurant front-desk virtual assistant for **La Bella Tavola**. The virtual assistant, frequently introducing itself as **Sarah Johnson**, strictly adheres to prompt-engineering constraints (no external Tools/RAG used) and orchestrates conversation state directly via FastAPI and WebSockets. The system gracefully handles context extraction, dietary preferences, modification/cancellation of reservations, and general queries entirely through natural language processing.

## 🚀 Setup Instructions

### Prerequisites
1. **Docker & Docker Compose**: Ensure [Docker Desktop](https://docs.docker.com/get-docker/) is installed and running on your machine.
2. **Ollama**: We use Ollama for local LLM orchestration. Install [Ollama](https://ollama.com/) and ensure the service is active.
3. **Model Weights**: Pull the specific AI model (`qwen:1.8b`) used by this system:
   ```bash
   ollama pull qwen:1.8b
   ```

### Running the System
1. Open a terminal in the project's root folder (`ember-refine`).
2. Build and start the backend and frontend containers:
   ```bash
   docker compose up --build -d
   ```
3. Open your browser and access the Restaurant Assistant at: **[http://localhost:3000](http://localhost:3000)**

*To stop the system later, run:*
```bash
docker compose down
```

## 🏗️ Architecture & Backend Workflow

The system is split into a modern React frontend and a robust Python/FastAPI backend, communicating strictly over WebSockets to provide real-time token streaming.

```mermaid
graph TD
    User([User]) -->|Interacts with UI| ReactApp[React Frontend / Browser]
    
    subgraph Frontend
        ReactApp -->|Displays Chat| UIComponents[Chat Interface]
        UIComponents <-->|WebSocket Connection| WSClient[Frontend WebSocket Client]
    end
    
    subgraph Backend - FastAPI
        WSClient <-->|JSON Stream| API[api.py: FastAPI WebSockets API]
        API <-->|State & History| SessionStore[In-Memory Session Store]
        API <-->|Route Message| ConvManager[conversation_manager.py: Logic Engine]
        
        ConvManager -->|1. Regex Extraction| Extractor[Signal Extractor\nDate/Time/Diet/Guests/Name]
        ConvManager -->|2. Next Stage| StateMachine[Finite State Machine]
        ConvManager <-->|3. Build Prompts| Templates[prompt_templates.py]
    end
    
    subgraph AI Inference - Ollama
        ConvManager <-->|HTTP POST (Stream)| OllamaEngine[Local LLM Engine - qwen:1.8b]
    end
```

### How Responses are Generated
The application avoids generic off-the-shelf "chat wrappers" and instead orchestrates the conversation via a **Finite State Machine (FSM)**.
1. **Input Reception**: The user types a message in the React UI, which is sent over a persistent WebSocket connection to the FastAPI backend.
2. **Signal Extraction & Intent Detection**: Before the LLM even sees the message, regular expressions scan the text for hard data (e.g., dates like "tomorrow", times like "8 pm", dietary needs like "lactose intolerant"). The intent (e.g., "new_reservation", "cancel_reservation") is classified.
3. **State Transitions**: Based on the missing data, the system moves between stages such as `collecting`, `confirming`, `confirmed`, `modifying`, etc.
4. **Prompt Construction**: The system dynamically builds a highly constrained system prompt containing ONLY the extracted memory, missing requirements, and specific few-shot examples corresponding to the *current FSM stage*.
5. **Local Inference (Ollama)**: This compiled prompt is sent to the local `qwen:1.8b` model process via an HTTP stream. The LLM generates the text answering the prompt (e.g., asking for the missing name, or confirming the final details).
6. **Token Streaming**: As Ollama emits each word/token, FastAPI instantly pushes it over the WebSocket back to the React UI, creating a fluid typing effect.

### Backend Python Modules Detailed

The backend logic is cleanly separated into three main Python files:

#### 1. `api.py` (The Network Layer)
- Serves as the entry point for the FastAPI application.
- Manages the WebSocket lifecycle (accepting connections, handling disconnects).
- Creates "on-the-fly" session IDs.
- Contains the asynchronous event loop that listens for user messages, hands them to the Conversation Manager, and streams the incoming tokens back to the frontend.
- Implements background model "warm-up" on server startup so the local LLM is loaded into RAM before the first user connects.

#### 2. `conversation_manager.py` (The Brain)
- Houses the core business logic, the Finite State Machine (`_next_stage`), and the regex configurations (`extract_signals`).
- Maintains an in-memory dictionary of all active user sessions, storing their conversation history and extracted variables (the slot-filling memory map).
- Implements aggressive `re.compile` expressions to accurately pull names, dates, times, party sizes, and specific complex dietary restrictions (e.g., "no dairy").
- Formulates the exact payload sent to the Ollama HTTP API, including constraints like `MAX_TOKENS = 250` and strategic `stop` sequences so the LLM doesn't hallucinate extra lines.

#### 3. `prompt_templates.py` (The Knowledge Base)
- Acts as the hardcoded database for all "La Bella Tavola" business rules, operating hours, dress restrictions, and constraints.
- Dynamically assembles the system prompt by combining the FSM stage instructions, current memory state, and the hardcoded business knowledge.
- Injects **Stage-Specific Few-Shot Examples**: To force the 1.8B parameter model to behave nicely, this module supplies exact formatted "Customer vs. Assistant" examples matching whatever the FSM is trying to achieve (e.g., if the state is `modifying` with no name, it explicitly shows the model examples of how to ask for a name politely in one sentence).

## 🧠 Model Selection

For this NLP assignment, we selected **Qwen 1.8B** (`qwen:1.8b`) hosted locally via `Ollama`. 

**Why Qwen 1.8B?**
- **Hardware Efficiency**: We needed a model that could run 100% locally on standard consumer CPU hardware without requiring dedicated GPUs. The 1.8B parameter size is the perfect sweet spot for CPU inference.
- **Instruction Following**: Despite its small footprint, Qwen 1.8B natively supports complex instruction tuning, allowing us to enforce STRICT formatting policies (e.g., "Reply in ONE short sentence only").
- **Cost & Privacy**: Running a quantized 4-bit GGUF model locally means zero API costs and total data privacy, fitting the constraints of a purely prompt-engineered system without external dependencies. 

## 📊 Performance Benchmarks & Realistic Expectations

Since this system runs entirely locally **without a dedicated GPU**, performance is bottlenecked by CPU computational limits.

| Metric | Measurement / Value |
|--------|---------------------|
| **Response Generation Time**| **Up to 20 - 40 seconds per turn.** |
| **Why is it slow?** | We are running a 1.8 billion parameter neural network strictly on a local CPU. The processor must calculate billions of floating-point operations sequentially to predict the next word. Without GPU parallelization, generating a 30-word response physically takes the CPU around 20-30 seconds. To counteract this, we implemented true WebSocket streaming so the user sees the bot typing in real-time rather than waiting indefinitely. |
| **Throughput** | ~2 - 4 tokens/sec on typical CPU |
| **Regex Extraction Speed** | < 0.05 seconds (instantaneous) |

## ⚠️ Known Limitations

1. **Hardware Dependent Response Times**: As mentioned above, response times for open-ended questions can take up to 20-40 seconds strictly due to the limitation of CPU-based local AI inference.
2. **Strict Regex Boundaries**: While we implemented aggressive regex for names, dietary restrictions, dates, and times, the system might struggle if a user inputs complex linguistic variations (e.g., "I am lactose intolerant and also allergic to peanuts") that aren't specifically caught by the predefined regex dictionary.
3. **No External RAG or Tools**: As per the assignment restrictions, the chatbot possesses no external database or API connectivity for live queries. All business rules, menus, and operating hours are hardcoded strictly within the prompt context window.
4. **State Persistence**: The current conversation memory and state tracking is held in-memory via Python dictionaries (`_sessions`). In a scalable production environment, this would need to be migrated to a distributed KV store like Redis.
5. **Context Window Limits**: Long conversations may eventually hit the token limit. We implemented a sliding window approach (`WINDOW_SIZE = 4`) that discards older chatter while keeping the deterministic memory dictionary intact, so the bot never forgets the reservation details even if it drops earlier conversational context.

---
*Developed for the Natural Language Processing Course assignment.*
