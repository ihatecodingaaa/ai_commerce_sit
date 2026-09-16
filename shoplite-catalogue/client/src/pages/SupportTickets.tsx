import React, { useState } from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { toast } from "sonner";

export default function SupportTickets() {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("normal");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    toast.success("Support ticket submitted! Ticket ID: #TK-8492");
  };

  return (
    <div className="page-wrap">
      <Header />
      <main className="content">
        <section className="hero animate-in" style={{ padding: "2rem" }}>
          <span className="hero-badge">Direct assistance</span>
          <h1>Support tickets</h1>
          <p>Need dedicated assistance? Submit a ticket and our engineering and support leads will get back to you.</p>
        </section>

        <div className="card auth-card" style={{ maxWidth: "600px" }}>
          <div className="accent-bar"></div>
          <h2>Open a support ticket</h2>
          <p className="muted" style={{ marginBottom: "1.25rem" }}>
            We typically respond within 24 hours on business days.
          </p>

          {submitted ? (
            <div style={{ textAlign: "center", padding: "1.5rem 0" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>✅</div>
              <h3>Ticket Received</h3>
              <p className="muted">
                Your ticket <strong>#TK-8492</strong> has been logged. We've sent a confirmation to your email.
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setSubmitted(false)}
                style={{ marginTop: "1rem" }}
              >
                Submit another ticket
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <label htmlFor="ticket-subject">Subject</label>
              <input
                id="ticket-subject"
                type="text"
                placeholder="Brief summary of the issue"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
              />

              <label htmlFor="ticket-priority">Priority</label>
              <select
                id="ticket-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="low">Low (General question)</option>
                <option value="normal">Normal (Order or shipping inquiry)</option>
                <option value="urgent">Urgent (Defective item or returns)</option>
              </select>

              <label htmlFor="ticket-message">Message details</label>
              <textarea
                id="ticket-message"
                rows={4}
                placeholder="Describe your issue or order question..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
              />

              <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: "1.4rem" }}>
                Submit ticket
              </button>
            </form>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
