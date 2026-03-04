import { Plus, Search, Image, LayoutGrid, Code2, FolderOpen, MessageSquare } from "lucide-react";

const navItems = [
  { icon: Plus, label: "New chat" },
  { icon: Search, label: "Search chats" },
  { icon: Image, label: "Images" },
  { icon: LayoutGrid, label: "Apps" },
  { icon: Code2, label: "Codex" },
  { icon: FolderOpen, label: "Projects" },
];

const chatHistory = [
  "Conversational AI System",
  "GPU vs CPU for Training",
  "Transfer Learning Celebrity D...",
  "Running errands meaning",
  "AI for Legal Startups",
  "Linear Regression Task",
  "Code Explanation Request",
  "BPE Tokenizer Training",
  "Correcting English Sentence",
];

const ChatSidebar = () => {
  return (
    <aside className="flex h-screen w-[260px] flex-col border-r border-border bg-background">
      {/* Top icons row */}
      <div className="flex items-center justify-between px-3 pt-3 pb-1">
        <button className="p-2 rounded-lg hover:bg-secondary transition-colors duration-200">
          <Code2 className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
        </button>
        <button className="p-2 rounded-lg hover:bg-secondary transition-colors duration-200">
          <Plus className="h-5 w-5 text-muted-foreground" strokeWidth={1.5} />
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex flex-col gap-0.5 px-2 pt-2">
        {navItems.map(({ icon: Icon, label }) => (
          <button
            key={label}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all duration-200"
          >
            <Icon className="h-[18px] w-[18px]" strokeWidth={1.5} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {/* Chat history */}
      <div className="mt-6 flex-1 overflow-y-auto px-2">
        <p className="px-3 pb-2 text-xs font-medium text-muted-foreground">Your chats</p>
        <div className="flex flex-col gap-0.5">
          {chatHistory.map((chat) => (
            <button
              key={chat}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-all duration-200 text-left truncate"
            >
              <MessageSquare className="h-4 w-4 shrink-0 opacity-50" strokeWidth={1.5} />
              <span className="truncate">{chat}</span>
            </button>
          ))}
        </div>
      </div>

      {/* User section */}
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-600 text-xs font-semibold text-white">
            HA
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">haider abbbas</p>
            <p className="text-xs text-muted-foreground">Free</p>
          </div>
          <button className="rounded-md border border-border bg-secondary px-3 py-1 text-xs font-medium text-foreground hover:bg-violet/10 hover:border-violet transition-all duration-200">
            Upgrade
          </button>
        </div>
      </div>
    </aside>
  );
};

export default ChatSidebar;
