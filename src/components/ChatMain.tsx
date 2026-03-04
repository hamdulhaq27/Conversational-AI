import { Plus, Mic, AudioLines, ChevronDown } from "lucide-react";

const ChatMain = () => {
  return (
    <div className="flex flex-1 flex-col h-screen bg-background">
      {/* Top bar */}
      <header className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-1">
          <span className="font-heading text-base font-semibold text-foreground">ChatGPT</span>
          <ChevronDown className="h-4 w-4 text-muted-foreground" strokeWidth={1.5} />
        </div>
        <div className="flex items-center gap-3">
          <button className="rounded-full border border-violet bg-violet/10 px-4 py-1.5 text-xs font-medium text-foreground hover:bg-violet/20 transition-all duration-200">
            ✦ Get Plus
          </button>
          <button className="p-2 rounded-lg hover:bg-secondary transition-colors duration-200">
            <svg className="h-5 w-5 text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </header>

      {/* Main content area */}
      <div className="flex flex-1 flex-col items-center justify-center px-4">
        <h2 className="font-heading text-2xl font-medium text-foreground mb-16">
          Ready when you are.
        </h2>
      </div>

      {/* Input area */}
      <div className="px-4 pb-6 pt-2">
        <div className="mx-auto max-w-3xl">
          <div className="relative flex items-center rounded-2xl border border-border bg-card px-4 py-3 shadow-lg" style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04), 0 4px 20px rgba(0,0,0,0.4)' }}>
            <button className="p-1.5 rounded-lg hover:bg-secondary transition-colors duration-200 mr-2">
              <Plus className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
            </button>
            <input
              type="text"
              placeholder="Ask anything"
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
            />
            <div className="flex items-center gap-2 ml-2">
              <button className="p-1.5 rounded-lg hover:bg-secondary transition-colors duration-200">
                <Mic className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
              </button>
              <button className="flex h-9 w-9 items-center justify-center rounded-full bg-foreground text-background transition-colors duration-200 hover:opacity-90">
                <AudioLines className="h-4 w-4" strokeWidth={2} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatMain;
