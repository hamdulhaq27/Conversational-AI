import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Code2, Layers, Zap, ArrowRight, Terminal, Shield, Sparkles } from "lucide-react";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b border-border bg-section nav-highlight">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-8">
            <span className="font-heading text-lg font-semibold tracking-tight text-foreground">
              Codex
            </span>
            <div className="hidden md:flex items-center gap-1">
              {["Features", "Challenges", "Pricing", "Docs"].map((item, i) => (
                <a
                  key={item}
                  href="#"
                  className={`px-3 py-2 text-sm font-medium transition-all duration-200 rounded-md ${
                    i === 0
                      ? "text-foreground border-b-2 border-violet"
                      : "text-muted-foreground hover:text-foreground hover:bg-violet-subtle"
                  }`}
                >
                  {item}
                </a>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm">
              Sign In
            </Button>
            <Button variant="default" size="sm">
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative py-24 md:py-32">
        <div className="container max-w-4xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-border px-4 py-1.5 mb-8">
            <Sparkles className="icon-style h-3.5 w-3.5" />
            <span className="text-xs font-medium text-muted-foreground">
              The premium coding platform
            </span>
          </div>
          <h1 className="text-foreground mb-6">
            Master code with
            <br />
            intention & clarity
          </h1>
          <p className="mx-auto max-w-2xl text-lg mb-10">
            A refined environment for developers who value precision,
            depth, and craft. Build skills that compound.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Button variant="hero">
              Start Building
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button variant="secondary" size="lg">
              View Challenges
            </Button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 section-bg">
        <div className="container max-w-5xl">
          <div className="text-center mb-14">
            <h2 className="text-foreground mb-2">Built for depth</h2>
            <span className="accent-underline mx-auto" />
            <p className="mt-4 max-w-lg mx-auto">
              Every detail considered. Every interaction refined.
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            {[
              {
                icon: Code2,
                title: "Structured Challenges",
                desc: "Curated problem sets that build real competence, not just syntax recall.",
              },
              {
                icon: Layers,
                title: "Progressive Depth",
                desc: "Layer complexity naturally. Each level builds on the foundations before it.",
              },
              {
                icon: Zap,
                title: "Instant Feedback",
                desc: "Real-time validation with precise diagnostics. Know exactly where you stand.",
              },
            ].map(({ icon: Icon, title, desc }) => (
              <Card key={title}>
                <CardHeader>
                  <Icon className="icon-style h-5 w-5 mb-3" strokeWidth={1.5} />
                  <CardTitle className="text-foreground">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm">{desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-20">
        <div className="container max-w-4xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: "12K+", label: "Developers" },
              { value: "340+", label: "Challenges" },
              { value: "98%", label: "Completion" },
              { value: "4.9", label: "Rating" },
            ].map(({ value, label }) => (
              <div key={label}>
                <div className="font-heading text-3xl font-semibold text-foreground">{value}</div>
                <div className="mt-1 text-sm text-muted-foreground">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 section-bg">
        <div className="container max-w-2xl text-center">
          <Terminal className="icon-style h-8 w-8 mx-auto mb-6" strokeWidth={1.5} />
          <h2 className="text-foreground mb-4">Ready to begin?</h2>
          <p className="mb-8">
            Join a community of developers who take their craft seriously.
          </p>
          <Button variant="hero">
            Get Started Free
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-10">
        <div className="container flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Shield className="icon-style h-4 w-4" strokeWidth={1.5} />
            <span className="text-sm text-muted-foreground">
              © 2026 Codex. All rights reserved.
            </span>
          </div>
          <div className="flex items-center gap-6">
            {["Privacy", "Terms", "Contact"].map((item) => (
              <a
                key={item}
                href="#"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-200"
              >
                {item}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Index;
