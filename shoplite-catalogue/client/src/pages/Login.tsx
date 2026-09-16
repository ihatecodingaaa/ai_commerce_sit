import React, { useState } from "react";
import { Link, useLocation } from "wouter";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { toast } from "sonner";

export default function Login() {
  const [, setLocation] = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success(`Welcome back, ${username || "friend"}!`);
    setTimeout(() => {
      setLocation("/products");
    }, 800);
  };

  return (
    <div className="page-wrap">
      <Header />
      <main className="content">
        <div className="card auth-card">
          <div className="accent-bar"></div>
          <h1>Welcome back</h1>
          <p className="muted" style={{ marginBottom: "1.25rem" }}>
            Log in to view your orders and chat with support.
          </p>
          <form onSubmit={handleSubmit}>
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              name="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: "1.4rem" }}>
              Log in
            </button>
          </form>
          <p className="muted" style={{ marginTop: "1.25rem", textAlign: "center" }}>
            No account? <Link href="/register" style={{ textDecoration: "underline" }}>Register</Link>
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
