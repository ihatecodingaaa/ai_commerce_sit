import React, { useState } from "react";
import { Link, useLocation } from "wouter";
import { Menu, Moon, Search, Sparkles, Sun, X } from "lucide-react";
import { LOGO_SVG } from "@/data/products";
import { useTheme } from "@/contexts/ThemeContext";

export function Header() {
  const [location] = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();

  const closeMenu = () => setMobileMenuOpen(false);
  const isActive = (path: string) => location === path || (path === "/products" && (location === "/" || location.startsWith("/products")));

  return (
    <header className="nav">
      <div className="nav-inner">
        <Link href="/products" className="brand" onClick={closeMenu}>
          <span className="brand-mark"><img src={LOGO_SVG} alt="" className="logo-mark-img" /></span>
          <span>ShopLite</span>
          <span className="brand-spark"><Sparkles size={12} strokeWidth={2.5} /></span>
        </Link>

        <button
          id="nav-toggle"
          className="nav-toggle"
          aria-label="Toggle navigation"
          aria-expanded={mobileMenuOpen}
          onClick={() => setMobileMenuOpen((open) => !open)}
        >
          {mobileMenuOpen ? <X size={19} /> : <Menu size={19} />}
        </button>

        <nav id="nav-links" className={`nav-links ${mobileMenuOpen ? "open" : ""}`}>
          <Link href="/products" className={isActive("/products") ? "active" : ""} onClick={closeMenu}>Products</Link>
          <Link href="/about" className={isActive("/about") ? "active" : ""} onClick={closeMenu}>About</Link>
          <Link href="/support" className={isActive("/support") ? "active" : ""} onClick={closeMenu}>Support</Link>
        </nav>

        <div className="auth-area">
          <button className="nav-icon" type="button" aria-label="Search products" title="Search products" onClick={() => document.getElementById("catalog-search")?.focus()}>
            <Search size={17} strokeWidth={2.2} />
          </button>
          <button
            className="nav-icon theme-toggle-control"
            id="theme-toggle"
            type="button"
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
            onClick={toggleTheme}
          >
            {theme === "dark" ? <Sun size={17} strokeWidth={2.2} /> : <Moon size={17} strokeWidth={2.2} />}
          </button>
          <Link href="/login" className="link-btn">Log in</Link>
          <Link href="/register" className="btn btn-primary btn-sm nav-join">Join the club <span>↗</span></Link>
        </div>
      </div>
    </header>
  );
}
