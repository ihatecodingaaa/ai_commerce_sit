import React, { useState } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

interface Message {
  id: number;
  sender: "bot" | "user";
  text: string;
}

export default function Support() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      sender: "bot",
      text: "Hi there! I'm Shopilot, your personal shopping assistant. Ask me anything about our gadgets, orders, or return policies!",
    },
  ]);
  const [input, setInput] = useState("");

  const handleSend = (textToSend?: string) => {
    const query = textToSend || input;
    if (!query.trim()) return;

    const userMsg: Message = { id: Date.now(), sender: "user", text: query };
    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput("");

    setTimeout(() => {
      let reply = "Our support team is always here to help! Small gadgets, big upgrades.";
      const lower = query.toLowerCase();
      if (lower.includes("shipping") || lower.includes("free")) {
        reply = "We offer free standard shipping on all orders over $50!";
      } else if (lower.includes("earbuds") || lower.includes("aurora")) {
        reply = "The Aurora Wireless Earbuds have 24h battery life and active noise cancellation for $59.99.";
      } else if (lower.includes("ssd") || lower.includes("nimbus")) {
        reply = "The Nimbus Portable SSD 1TB offers speeds up to 1050MB/s and shock resistance for $89.99.";
      } else if (lower.includes("return") || lower.includes("policy")) {
        reply = "We have a 30-day hassle-free return policy on all hardware in original packaging.";
      }

      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, sender: "bot", text: reply },
      ]);
    }, 600);
  };

  return (
    <div className="page-wrap">
      <Header />
      <main className="content">
        <section className="hero animate-in" style={{ padding: "2rem" }}>
          <span className="hero-badge">24/7 Virtual Assistant</span>
          <h1>Chat with Shopilot</h1>
          <p>Instant answers to all your gear and order questions.</p>
        </section>

        <div className="card" style={{ maxWidth: "700px", margin: "0 auto", overflow: "hidden" }}>
          <div
            style={{
              padding: "0.85rem 1rem",
              borderBottom: "1px solid var(--border)",
              background: "var(--surface-2)",
              display: "flex",
              alignItems: "center",
              gap: "0.6rem",
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "linear-gradient(135deg, var(--brand-500), var(--brand-700))",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
              }}
            >
              🤖
            </div>
            <div>
              <strong style={{ fontSize: "0.92rem", display: "block" }}>Shopilot</strong>
              <span style={{ fontSize: "0.75rem", color: "var(--text-faint)", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", display: "inline-block" }}></span>
                Online
              </span>
            </div>
          </div>

          <div
            style={{
              height: "360px",
              overflowY: "auto",
              padding: "1rem",
              background: "var(--surface-2)",
              display: "flex",
              flexDirection: "column",
              gap: "0.75rem",
            }}
          >
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  padding: "0.6rem 0.9rem",
                  borderRadius: 14,
                  maxWidth: "75%",
                  fontSize: "0.92rem",
                  marginLeft: m.sender === "user" ? "auto" : "0",
                  marginRight: m.sender === "bot" ? "auto" : "0",
                  background:
                    m.sender === "user"
                      ? "linear-gradient(135deg, var(--brand-500), var(--brand-700))"
                      : "var(--surface)",
                  color: m.sender === "user" ? "#ffffff" : "var(--text)",
                  border: m.sender === "bot" ? "1px solid var(--border)" : "none",
                  borderBottomRightRadius: m.sender === "user" ? 4 : 14,
                  borderBottomLeftRadius: m.sender === "bot" ? 4 : 14,
                }}
              >
                {m.text}
              </div>
            ))}
          </div>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.4rem",
              padding: "0.6rem 0.85rem",
              borderTop: "1px solid var(--border)",
              background: "var(--surface)",
            }}
          >
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ borderRadius: "999px", fontSize: "0.75rem" }}
              onClick={() => handleSend("What are the shipping costs?")}
            >
              Shipping policy?
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ borderRadius: "999px", fontSize: "0.75rem" }}
              onClick={() => handleSend("Tell me about Aurora Earbuds")}
            >
              Aurora Wireless Earbuds
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ borderRadius: "999px", fontSize: "0.75rem" }}
              onClick={() => handleSend("How fast is the Nimbus SSD?")}
            >
              Nimbus Portable SSD
            </button>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            style={{
              display: "flex",
              gap: "0.5rem",
              padding: "0.6rem",
              borderTop: "1px solid var(--border)",
              background: "var(--surface)",
            }}
          >
            <input
              type="text"
              placeholder="Ask about products, orders, shipping..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              style={{ borderRadius: "999px", padding: "0.5rem 0.9rem" }}
            />
            <button type="submit" className="btn btn-primary" style={{ borderRadius: "999px", padding: "0.5rem 1.1rem" }}>
              Send
            </button>
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}
