import ChatSidebar from "@/components/ChatSidebar";
import ChatMain from "@/components/ChatMain";

const Index = () => {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ChatSidebar />
      <ChatMain />
    </div>
  );
};

export default Index;
