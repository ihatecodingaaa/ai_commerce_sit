import React from "react";
import { Link } from "wouter";
import { LOGO_SVG } from "@/data/products";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div className="brand">
            <img src={LOGO_SVG} alt="" className="logo-mark-img" /> ShopLite
          </div>
          <p>Small gadgets, big upgrades.</p>
        </div>
        <div className="footer-col">
          <div className="footer-col-title">Company</div>
          <Link href="/about">About</Link>
        </div>
        <div className="footer-col">
          <div className="footer-col-title">Help</div>
          <Link href="/support">Chat with Shopilot</Link>
          <Link href="/support/tickets">Support tickets</Link>
        </div>
      </div>
      <div className="footer-bottom">
        &copy; 2026 ShopLite. All rights reserved.
      </div>
    </footer>
  );
}
