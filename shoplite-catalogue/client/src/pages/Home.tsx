import React, { useMemo, useState } from "react";
import { Link } from "wouter";
import { ArrowUpRight, Headphones, Search, ShieldCheck, SlidersHorizontal, Sparkles, Star, Truck, Zap } from "lucide-react";
import { toast } from "sonner";
import { PRODUCTS } from "@/data/products";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

const categories = ["All", ...Array.from(new Set(PRODUCTS.map((product) => product.category)))];

export default function Home() {
  const [activeCategory, setActiveCategory] = useState("All");
  const [query, setQuery] = useState("");
  const [savedProducts, setSavedProducts] = useState<number[]>([]);

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return PRODUCTS.filter((product) => {
      const matchesCategory = activeCategory === "All" || product.category === activeCategory;
      const matchesQuery = !normalizedQuery || `${product.name} ${product.category} ${product.description}`.toLowerCase().includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [activeCategory, query]);

  const toggleSaved = (id: number) => {
    setSavedProducts((saved) => saved.includes(id) ? saved.filter((savedId) => savedId !== id) : [...saved, id]);
  };

  return (
    <div className="page-wrap home-page">
      <Header />
      <main className="content">
        <section className="home-hero animate-in">
          <div className="hero-grid-lines" aria-hidden="true" />
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-dot" /> Curated tech, no clutter</div>
            <h1>Small gadgets.<br /><span>Big upgrades.</span></h1>
            <p>Meet the smart little things that make everyday life feel lighter, faster, and a whole lot more fun.</p>
            <div className="hero-actions">
              <a href="#catalog" className="btn btn-primary hero-cta">Explore the drop <ArrowUpRight size={17} /></a>
              <Link href="/about" className="hero-text-link">Why ShopLite <span>→</span></Link>
            </div>
            <div className="hero-proof">
              <div className="avatar-stack"><span>AM</span><span>JT</span><span>RK</span><span>+</span></div>
              <div><strong>Loved by 12k+ everyday explorers</strong><span>4.9 average rating from verified buyers</span></div>
            </div>
          </div>

          <div className="hero-showcase" aria-label="Featured Aurora Wireless Earbuds">
            <div className="showcase-glow" />
            <div className="showcase-ring showcase-ring-one" />
            <div className="showcase-ring showcase-ring-two" />
            <div className="hero-product-image"><img src={PRODUCTS[0].image} alt="Aurora Wireless Earbuds" /></div>
            <div className="floating-widget widget-top"><span className="widget-icon mint"><Zap size={14} fill="currentColor" /></span><span><strong>New drop</strong><small>Just landed today</small></span></div>
            <div className="floating-widget widget-bottom"><span className="widget-icon yellow"><Star size={14} fill="currentColor" /></span><span><strong>4.9/5</strong><small>1.2k happy ears</small></span></div>
            <div className="showcase-caption"><span>01 / 06</span><span>Aurora Wireless Earbuds</span></div>
          </div>
        </section>

        <section className="benefit-strip animate-in" aria-label="ShopLite benefits">
          <div className="benefit-item"><span className="benefit-icon"><Truck size={18} /></span><span><strong>Free shipping</strong><small>On orders over $50</small></span></div>
          <div className="benefit-item"><span className="benefit-icon"><ShieldCheck size={18} /></span><span><strong>30-day returns</strong><small>Try it, love it, or send it back</small></span></div>
          <div className="benefit-item"><span className="benefit-icon"><Headphones size={18} /></span><span><strong>Human support</strong><small>Real help from real people</small></span></div>
          <div className="benefit-score"><span>4.9</span><div><span className="stars">★★★★★</span><small>customer score</small></div></div>
        </section>

        <section className="catalog-section" id="catalog">
          <div className="catalog-heading">
            <div><div className="eyebrow eyebrow-dark">The everyday edit</div><h2>Find your next <span>favorite.</span></h2><p>Six tiny upgrades, carefully picked for the way you actually live.</p></div>
            <div className="catalog-controls">
              <label className="search-box"><Search size={16} /><input id="catalog-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the edit..." /></label>
              <button className="filter-button" type="button" onClick={() => toast.info("Use the category chips to filter the edit.")}><SlidersHorizontal size={16} /> <span>Filters</span></button>
            </div>
          </div>
          <div className="category-row" role="tablist" aria-label="Product categories">
            {categories.map((category) => <button key={category} type="button" role="tab" aria-selected={activeCategory === category} className={`category-filter ${activeCategory === category ? "active" : ""}`} onClick={() => setActiveCategory(category)}>{category}<span>{category === "All" ? PRODUCTS.length : PRODUCTS.filter((product) => product.category === category).length}</span></button>)}
          </div>

          {filteredProducts.length > 0 ? (
            <div className="product-grid upgraded-grid stagger">
              {filteredProducts.map((product, index) => (
                <Link key={product.id} href={`/products/${product.id}`} className={`product-card premium-card card-tone-${(product.id % 4) + 1}`} style={{ animationDelay: `${index * 55}ms` }}>
                  <div className="product-card-topline"><span className="category-badge">{product.category}</span><button type="button" className={`save-button ${savedProducts.includes(product.id) ? "saved" : ""}`} aria-label={`Save ${product.name}`} onClick={(event) => { event.preventDefault(); toggleSaved(product.id); }}>{savedProducts.includes(product.id) ? "♥" : "♡"}</button></div>
                  <div className="product-thumb"><img src={product.image} alt={product.name} loading="lazy" /><span className="thumb-sheen" /></div>
                  <div className="product-card-body"><h3>{product.name}</h3><p className="desc">{product.description}</p><div className="card-meta"><span className="stars">★★★★<span className="star-empty">★</span></span><span className="review-count">{product.reviewCount ? `${product.reviewCount} review` : "New"}</span></div><div className="price-row"><div className="price">${product.price.toFixed(2)}</div><span className="card-arrow"><ArrowUpRight size={16} /></span></div></div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-state search-empty"><Sparkles size={26} /><h3>No gadgets found</h3><p>Try a different search or browse all of the edit.</p><button className="btn btn-secondary btn-sm" type="button" onClick={() => { setQuery(""); setActiveCategory("All"); }}>Reset search</button></div>
          )}
        </section>

        <section className="newsletter-card animate-in">
          <div><div className="eyebrow">The good stuff, occasionally</div><h2>Get first dibs on the next drop.</h2><p>Fresh finds, tiny discounts, zero spam. Promise.</p></div>
          <form onSubmit={(event) => { event.preventDefault(); toast.success("You're on the list — welcome to the good stuff!"); }} className="newsletter-form"><input type="email" placeholder="you@example.com" aria-label="Email address" required /><button className="btn btn-primary" type="submit">Keep me posted <ArrowUpRight size={16} /></button></form>
        </section>
      </main>
      <Footer />
    </div>
  );
}
