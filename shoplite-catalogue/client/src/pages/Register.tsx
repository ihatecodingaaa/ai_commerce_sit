import React, { useState } from "react";
import { Link, useLocation } from "wouter";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { toast } from "sonner";

export default function Register() {
  const [, setLocation] = useLocation();
  const [formData, setFormData] = useState({
    fullName: "",
    username: "",
    email: "",
    password: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success("Account created successfully!");
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
          <h1>Create an account</h1>
          <p className="muted" style={{ marginBottom: "1.25rem" }}>
            Join ShopLite to buy, review, and get support.
          </p>
          <form onSubmit={handleSubmit}>
            <label htmlFor="fullName">Full name</label>
            <input
              id="fullName"
              type="text"
              name="fullName"
              value={formData.fullName}
              onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
              required
              autoFocus
            />
            <label htmlFor="reg-username">Username</label>
            <input
              id="reg-username"
              type="text"
              name="username"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              required
            />
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              name="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
            />
            <label htmlFor="reg-password">Password</label>
            <input
              id="reg-password"
              type="password"
              name="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
            />
            <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: "1.4rem" }}>
              Create account
            </button>
          </form>
          <p className="muted" style={{ marginTop: "1.25rem", textAlign: "center" }}>
            Already have an account? <Link href="/login" style={{ textDecoration: "underline" }}>Log in</Link>
          </p>
        </div>
      </main>
      <Footer />
    </div>
  );
}
