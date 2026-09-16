import React from "react";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

export default function About() {
  return (
    <div className="page-wrap">
      <Header />
      <main className="content">
        <section className="hero animate-in">
          <span className="hero-badge">Our story</span>
          <h1>Small team, small gadgets, big opinions about cable management.</h1>
          <p>Small gadgets, big upgrades &mdash; that's the whole pitch, really.</p>
        </section>

        <div className="card animate-in" style={{ padding: "1.5rem 1.75rem", marginBottom: "1.5rem" }}>
          <h2 style={{ marginTop: 0 }}>How ShopLite happened</h2>
          <p>
            The whole thing started, as these things often do, with a broken pair of
            earbuds and a spreadsheet. <strong>Alice Tan</strong> was three weeks into
            a job she didn't love, running customer support for a company that made
            her read from a script, when her charging case died for the second time
            that month. She mentioned it to <strong>Priya Nair</strong> at a Saturday
            coworking meetup &mdash; the kind with bad coffee and good whiteboards
            &mdash; and by the end of the afternoon they'd sketched out something
            neither of them expected to actually build: a tiny electronics shop that
            didn't treat "customer support" as an afterthought bolted onto checkout.
          </p>
          <p>
            Priya wrote the first version of the product catalog over a long weekend.
            It had four products, a font nobody liked, and exactly one payment
            method. It also, crucially, worked. Alice handled every single support
            email personally for the first six months, which is either a great way
            to understand your customers or a terrible way to sleep, and honestly it
            was some of both.
          </p>
          <p>
            <strong>Marcus Webb</strong> joined not long after, mostly because he
            kept "just taking a look" at why the site fell over every time it got
            linked from anywhere, and eventually someone pointed out that he'd
            unofficially been doing the job for a month already. He's been keeping
            the servers upright ever since, with what he describes as "a healthy
            amount of paranoia and a slightly less healthy amount of coffee."
          </p>
          <p>
            By the time <strong>Dana Okafor</strong> came on to build out a real
            support team, ShopLite had outgrown the "Alice answers everything
            personally" model, if only because Alice had started answering things at
            2am and everyone agreed that needed to stop. Dana's first project was
            turning six months of Alice's support notes into an actual knowledge
            base &mdash; the same one, more or less, that the support chat on this
            site still searches today.
          </p>
          <p className="muted" style={{ marginBottom: 0 }}>
            Same four people, still arguing about cable management. Some things don't change.
          </p>
        </div>

        <div className="card animate-in" style={{ padding: "1.5rem 1.75rem", marginBottom: "1.5rem" }}>
          <h2 style={{ marginTop: 0 }}>Milestones</h2>
          <ul className="employee-list">
            <li>
              <span className="category-badge" style={{ flexShrink: 0 }}>2019</span>
              <div>ShopLite ships with four products and one very tired founder answering every email.</div>
            </li>
            <li>
              <span className="category-badge" style={{ flexShrink: 0 }}>2020</span>
              <div>Marcus formally joins as the site stops falling over quite so often.</div>
            </li>
            <li>
              <span className="category-badge" style={{ flexShrink: 0 }}>2021</span>
              <div>Dana builds the first real knowledge base out of a year of support notes.</div>
            </li>
            <li>
              <span className="category-badge" style={{ flexShrink: 0 }}>2022</span>
              <div>Catalog grows past 100 products; earbuds remain, appropriately, a bestseller.</div>
            </li>
            <li>
              <span className="category-badge" style={{ flexShrink: 0 }}>Today</span>
              <div>Still a small team, still answering questions &mdash; now with a chat assistant to help.</div>
            </li>
          </ul>
        </div>

        <h2 style={{ marginTop: "2rem" }}>Our team</h2>
        <div className="team-grid stagger">
          <div className="card team-card">
            <div className="team-card-photo" style={{ background: "linear-gradient(135deg, #0b3b36, #14958a)", color: "#fff" }}>
              👩‍💼
            </div>
            <div className="team-card-body">
              <strong>Alice Tan</strong>
              <span className="muted" style={{ fontSize: "0.82rem" }}>Head of Customer Operations</span>
              <span className="category-badge" style={{ marginTop: "0.4rem" }}>Customer Operations</span>
            </div>
          </div>
          <div className="card team-card">
            <div className="team-card-photo" style={{ background: "linear-gradient(135deg, #1e293b, #334155)", color: "#fff" }}>
              👩‍💻
            </div>
            <div className="team-card-body">
              <strong>Priya Nair</strong>
              <span className="muted" style={{ fontSize: "0.82rem" }}>Platform Engineer</span>
              <span className="category-badge" style={{ marginTop: "0.4rem" }}>Infrastructure</span>
            </div>
          </div>
          <div className="card team-card">
            <div className="team-card-photo" style={{ background: "linear-gradient(135deg, #0f766e, #115e59)", color: "#fff" }}>
              👨‍💻
            </div>
            <div className="team-card-body">
              <strong>Marcus Webb</strong>
              <span className="muted" style={{ fontSize: "0.82rem" }}>Site Reliability Engineer</span>
              <span className="category-badge" style={{ marginTop: "0.4rem" }}>Infrastructure</span>
            </div>
          </div>
          <div className="card team-card">
            <div className="team-card-photo" style={{ background: "linear-gradient(135deg, #b45309, #d97706)", color: "#fff" }}>
              👩‍💼
            </div>
            <div className="team-card-body">
              <strong>Dana Okafor</strong>
              <span className="muted" style={{ fontSize: "0.82rem" }}>Support Lead</span>
              <span className="category-badge" style={{ marginTop: "0.4rem" }}>Customer Support</span>
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
