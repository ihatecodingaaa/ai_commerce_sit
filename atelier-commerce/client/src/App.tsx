import { useEffect, useMemo, useState } from "react";
import { Route, Switch, useLocation } from "wouter";
import { motion, AnimatePresence } from "framer-motion";
import { Toaster, toast } from "sonner";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  CreditCard,
  FilePenLine,
  Heart,
  Inbox,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Mail,
  MapPin,
  Menu,
  MessageSquare,
  Minus,
  Moon,
  Package,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  ShoppingBag,
  SlidersHorizontal,
  Sparkles,
  Star,
  Sun,
  Tag,
  Trash2,
  Truck,
  UserCog,
  UserRound,
  WandSparkles,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AIChatBox, type Message } from "@/components/AIChatBox";
import { startLogin } from "@/const";

const images = {
  editorial: "/manus-storage/editorial-still_b692b097.jpg",
  travel: "/manus-storage/sand-travel-bag_7f4b8998.jpg",
  objects: "/manus-storage/onyx-objects_73d8b261.jpg",
};

type Product = {
  id: string;
  name: string;
  category: string;
  price: number;
  description: string;
  image: string;
  tone: string;
  badge?: string;
  stock: number;
  rating: number;
};

type Ticket = {
  id: string;
  subject: string;
  category: string;
  status: "Open" | "In progress" | "Resolved";
  date: string;
};

const initialProducts: Product[] = [
  { id: "mara", name: "Mara sculptural tote", category: "Bags", price: 420, description: "A softly structured carryall in full-grain Italian leather, finished with a hand-turned clasp.", image: images.travel, tone: "Sand", badge: "Best seller", stock: 18, rating: 4.9 },
  { id: "lumen", name: "Lumen drop earrings", category: "Jewelry", price: 180, description: "Brushed gold-plated silver with a quiet architectural profile designed for all-day wear.", image: images.editorial, tone: "Gold", badge: "New arrival", stock: 42, rating: 4.8 },
  { id: "onyx", name: "Onyx ritual objects", category: "Home", price: 260, description: "A considered set of stone, glass, and brass objects for the modern, tactile interior.", image: images.objects, tone: "Onyx", stock: 9, rating: 4.7 },
  { id: "alba", name: "Alba travel case", category: "Travel", price: 340, description: "A compact, considered case for the essentials that follow you everywhere.", image: images.travel, tone: "Ivory", stock: 22, rating: 4.9 },
  { id: "vega", name: "Vega chain bracelet", category: "Jewelry", price: 145, description: "A sculpted chain with softened edges and a signature hidden closure.", image: images.editorial, tone: "Saffron", stock: 35, rating: 4.6 },
  { id: "nadir", name: "Nadir incense set", category: "Home", price: 95, description: "Dark wood, mineral incense, and a stone tray for an evening ritual.", image: images.objects, tone: "Charcoal", stock: 14, rating: 4.8 },
];

const initialTickets: Ticket[] = [
  { id: "AT-1048", subject: "Exchange request for Mara tote", category: "Orders & returns", status: "In progress", date: "17 Sep 2026" },
  { id: "AT-1034", subject: "Care instructions for leather", category: "Product care", status: "Resolved", date: "12 Sep 2026" },
  { id: "AT-1027", subject: "Delivery address update", category: "Shipping", status: "Open", date: "09 Sep 2026" },
];

const navItems = [
  { label: "Shop", href: "/products" },
  { label: "Our story", href: "/about" },
  { label: "Support", href: "/support" },
];

const money = (value: number) => `$${value.toLocaleString("en-US")}`;

function App() {
  const [dark, setDark] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [cart, setCart] = useState<string[]>(["mara"]);
  const [products, setProducts] = useState<Product[]>(initialProducts);
  const [tickets, setTickets] = useState<Ticket[]>(initialTickets);
  const [demoUser, setDemoUser] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("atelier-theme");
    const storedCart = localStorage.getItem("atelier-cart");
    if (stored === "dark") setDark(true);
    if (storedCart) setCart(JSON.parse(storedCart));
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("atelier-theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    localStorage.setItem("atelier-cart", JSON.stringify(cart));
  }, [cart]);

  const addToCart = (id: string) => {
    setCart((current) => [...current, id]);
    const product = products.find((item) => item.id === id);
    toast.success(`${product?.name ?? "Item"} added to bag`, { description: "You can review it from the bag icon." });
  };

  const removeFromCart = (id: string) => {
    setCart((current) => {
      const index = current.indexOf(id);
      if (index === -1) return current;
      return [...current.slice(0, index), ...current.slice(index + 1)];
    });
  };

  const clearCart = () => setCart([]);

  return (
    <TooltipProvider>
      <Toaster position="bottom-right" toastOptions={{ className: "atelier-toast" }} />
      <div className="min-h-screen bg-background text-foreground selection:bg-[#d8bf98] selection:text-[#171717]">
        <SiteHeader dark={dark} setDark={setDark} cartCount={cart.length} menuOpen={menuOpen} setMenuOpen={setMenuOpen} />
        <AnimatePresence mode="wait">
          <Switch>
            <Route path="/" component={() => <HomePage addToCart={addToCart} />} />
            <Route path="/products" component={() => <ProductsPage products={products} addToCart={addToCart} />} />
            <Route path="/product/:id" component={() => <ProductPage products={products} addToCart={addToCart} />} />
            <Route path="/about" component={AboutPage} />
            <Route path="/support" component={() => <SupportPage tickets={tickets} setTickets={setTickets} />} />
            <Route path="/ai-concierge" component={ConciergePage} />
            <Route path="/auth" component={() => <AuthPage onAuth={() => setDemoUser(true)} />} />
            <Route path="/cart" component={() => <CartPage products={products} cart={cart} removeFromCart={removeFromCart} clearCart={clearCart} />} />
            <Route path="/account" component={() => <AccountPage demoUser={demoUser} setDemoUser={setDemoUser} />} />
            <Route path="/account/profile" component={() => <ProfilePage demoUser={demoUser} setDemoUser={setDemoUser} />} />
            <Route path="/admin" component={() => <AdminPage products={products} setProducts={setProducts} tickets={tickets} setTickets={setTickets} />} />
            <Route component={NotFoundPage} />
          </Switch>
        </AnimatePresence>
        <SiteFooter />
      </div>
    </TooltipProvider>
  );
}

function SiteHeader({ dark, setDark, cartCount, menuOpen, setMenuOpen }: { dark: boolean; setDark: (value: boolean) => void; cartCount: number; menuOpen: boolean; setMenuOpen: (value: boolean) => void }) {
  const [, setLocation] = useLocation();
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/90 backdrop-blur-xl">
      <div className="container flex h-[76px] items-center justify-between gap-8">
        <button className="flex items-center gap-3" onClick={() => setLocation("/")} aria-label="Atelier home">
          <span className="brand-mark">A</span>
          <span className="hidden text-[13px] font-semibold uppercase tracking-[0.28em] sm:block">Atelier</span>
        </button>
        <nav className="hidden items-center gap-9 text-[13px] font-medium tracking-[0.03em] md:flex">
          {navItems.map((item) => <button key={item.href} className="nav-link" onClick={() => setLocation(item.href)}>{item.label}</button>)}
        </nav>
        <div className="flex items-center gap-1 sm:gap-2">
          <button className="icon-button hidden sm:flex" aria-label="Search" onClick={() => setLocation("/products")}><Search size={18} /></button>
          <button className="icon-button" aria-label="Toggle theme" onClick={() => setDark(!dark)}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
          <button className="icon-button" aria-label="Account" onClick={() => setLocation("/account")}><UserRound size={18} /></button>
          <button className="icon-button relative" aria-label="Shopping bag" onClick={() => setLocation("/cart")}><ShoppingBag size={18} />{cartCount > 0 && <span className="count-dot">{cartCount}</span>}</button>
          <button className="icon-button md:hidden" aria-label="Menu" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={19} /> : <Menu size={19} />}</button>
        </div>
      </div>
      <AnimatePresence>
        {menuOpen && <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="border-t border-border bg-background md:hidden">
          <div className="container grid gap-1 py-4">
            {navItems.map((item) => <button key={item.href} className="mobile-nav-link" onClick={() => { setLocation(item.href); setMenuOpen(false); }}>{item.label}<ArrowUpRight size={15} /></button>)}
            <button className="mobile-nav-link" onClick={() => { setLocation("/ai-concierge"); setMenuOpen(false); }}>AI concierge<Sparkles size={15} /></button>
          </div>
        </motion.div>}
      </AnimatePresence>
    </header>
  );
}

function HomePage({ addToCart }: { addToCart: (id: string) => void }) {
  const [, setLocation] = useLocation();
  return <PageFrame className="overflow-hidden">
    <section className="container grid min-h-[640px] items-center gap-14 py-16 lg:grid-cols-[1.05fr_.95fr] lg:py-24">
      <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .6 }} className="relative z-10">
        <p className="eyebrow">Objects with intention · 2026</p>
        <h1 className="display-heading mt-6 max-w-[680px]">A quieter kind of <em>luxury.</em></h1>
        <p className="body-lead mt-7 max-w-[510px]">Thoughtful objects for the rituals that shape your day. Designed in small, considered runs and made to be kept.</p>
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Button className="premium-button" onClick={() => setLocation("/products")}>Explore the collection <ArrowUpRight size={16} /></Button>
          <button className="text-link" onClick={() => setLocation("/about")}>The Atelier philosophy <ArrowRight size={15} /></button>
        </div>
        <div className="mt-14 grid max-w-[500px] grid-cols-3 border-t border-border pt-6">
          {["01", "02", "03"].map((number, index) => <div key={number} className="pr-4"><span className="micro-label">{number}</span><p className="mt-2 text-[13px] leading-5 text-muted-foreground">{["Material-first design", "Small batch making", "A human aftercare team"][index]}</p></div>)}
        </div>
      </motion.div>
      <motion.div initial={{ opacity: 0, scale: .98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .8, delay: .08 }} className="relative">
        <div className="hero-image-wrap"><img src={images.editorial} alt="Editorial still life from the Atelier collection" className="hero-image" /><div className="hero-overlay" /></div>
        <div className="hero-caption"><span>Field note / 01</span><span>Paris · 48.8566° N</span></div>
        <div className="floating-note"><Sparkles size={15} /><span>New edit<br /><strong>Objects for September</strong></span></div>
      </motion.div>
    </section>
    <section className="border-y border-border bg-secondary/40">
      <div className="container grid gap-8 py-14 md:grid-cols-[1fr_2.2fr] md:items-center"><div><p className="eyebrow">A considered edit</p><h2 className="section-heading mt-3 max-w-[260px]">The pieces we keep close.</h2></div><div className="grid gap-6 sm:grid-cols-3">{["The daily carry", "The quiet ritual", "The considered gift"].map((title, index) => <button key={title} onClick={() => setLocation("/products")} className="group border-t border-border pt-4 text-left transition-colors hover:border-foreground"><span className="micro-label">0{index + 1}</span><div className="mt-8 flex items-end justify-between"><span className="font-serif text-[20px] italic">{title}</span><ArrowUpRight size={17} className="transition-transform group-hover:-translate-y-1 group-hover:translate-x-1" /></div></button>)}</div></div>
    </section>
    <section className="container py-20 lg:py-28">
      <div className="flex flex-wrap items-end justify-between gap-6"><div><p className="eyebrow">The current edit</p><h2 className="section-heading mt-3">Objects with a point of view.</h2></div><button className="text-link" onClick={() => setLocation("/products")}>View all pieces <ArrowRight size={15} /></button></div>
      <div className="mt-10 grid gap-5 md:grid-cols-3">{initialProducts.slice(0, 3).map((product, index) => <ProductCard key={product.id} product={product} addToCart={addToCart} index={index} />)}</div>
    </section>
    <section className="container pb-20"><div className="dark-panel grid gap-10 overflow-hidden lg:grid-cols-[1.1fr_.9fr] lg:items-center"><div className="relative z-10 p-9 sm:p-14"><p className="eyebrow text-[#d8bf98]">The Atelier concierge</p><h2 className="mt-4 max-w-[480px] font-serif text-4xl leading-[.98] tracking-[-.03em] text-white sm:text-5xl">A little help finding the right thing.</h2><p className="mt-6 max-w-[420px] text-[15px] leading-7 text-white/65">Ask our AI concierge about fit, care, gifting, or building a considered set. It knows the collection by heart.</p><Button className="mt-8 border border-white/20 bg-white text-[#161616] hover:bg-[#d8bf98]" onClick={() => setLocation("/ai-concierge")}>Meet the concierge <Sparkles size={16} /></Button></div><div className="relative min-h-[290px] overflow-hidden"><img src={images.objects} alt="Onyx ritual objects" className="absolute inset-0 h-full w-full object-cover opacity-70" /><div className="absolute inset-0 bg-gradient-to-r from-[#161616] via-transparent to-transparent" /></div></div></section>
  </PageFrame>;
}

function ProductsPage({ products, addToCart }: { products: Product[]; addToCart: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All pieces");
  const [sort, setSort] = useState("Featured");
  const categories = ["All pieces", ...Array.from(new Set(products.map((item) => item.category)))];
  const filtered = useMemo(() => products.filter((product) => (category === "All pieces" || product.category === category) && `${product.name} ${product.category}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === "Price: low to high" ? a.price - b.price : sort === "Price: high to low" ? b.price - a.price : 0), [products, category, query, sort]);
  return <PageFrame><section className="container py-14 lg:py-20"><div className="max-w-[720px]"><p className="eyebrow">The collection</p><h1 className="page-heading mt-4">A considered edit<br /><em>for everyday rituals.</em></h1><p className="body-lead mt-6 max-w-[560px]">Small-run pieces across carry, adornment, travel, and home. No excess. Just good materials and a little more thought.</p></div><div className="mt-14 flex flex-col gap-4 border-y border-border py-4 lg:flex-row lg:items-center lg:justify-between"><div className="flex flex-wrap gap-2">{categories.map((item) => <button key={item} onClick={() => setCategory(item)} className={`filter-chip ${category === item ? "filter-chip-active" : ""}`}>{item}</button>)}</div><div className="flex gap-3"><label className="search-field"><Search size={15} /><input placeholder="Search pieces" value={query} onChange={(e) => setQuery(e.target.value)} /></label><label className="sort-field"><SlidersHorizontal size={14} /><select value={sort} onChange={(e) => setSort(e.target.value)}><option>Featured</option><option>Price: low to high</option><option>Price: high to low</option></select></label></div></div><div className="mt-10 grid gap-x-5 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">{filtered.map((product, index) => <ProductCard key={product.id} product={product} addToCart={addToCart} index={index} />)}</div>{filtered.length === 0 && <div className="empty-state"><Search size={24} /><p>No pieces match that search.</p><button className="text-link" onClick={() => { setQuery(""); setCategory("All pieces"); }}>Reset filters <RotateCcw size={14} /></button></div>}</section></PageFrame>;
}

function ProductCard({ product, addToCart, index = 0 }: { product: Product; addToCart: (id: string) => void; index?: number }) {
  const [, setLocation] = useLocation();
  return <motion.article initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .35, delay: index * .05 }} className="product-card"><button className="product-image-wrap" onClick={() => setLocation(`/product/${product.id}`)}><img src={product.image} alt={product.name} className="product-image" /><div className="product-image-meta"><span>{product.tone}</span>{product.badge && <Badge className="editorial-badge">{product.badge}</Badge>}</div><span className="quick-view">View piece <ArrowUpRight size={14} /></span></button><div className="mt-4 flex items-start justify-between gap-4"><button className="text-left" onClick={() => setLocation(`/product/${product.id}`)}><p className="font-medium tracking-[-.01em]">{product.name}</p><p className="mt-1 text-[13px] text-muted-foreground">{product.category}</p></button><span className="font-medium">{money(product.price)}</span></div><div className="mt-4 flex items-center justify-between"><span className="flex items-center gap-1 text-[12px] text-muted-foreground"><Star size={12} fill="currentColor" /> {product.rating}</span><button className="product-add" onClick={() => addToCart(product.id)}>Add to bag <Plus size={14} /></button></div></motion.article>;
}

function ProductPage({ products, addToCart }: { products: Product[]; addToCart: (id: string) => void }) {
  const [, setLocation] = useLocation();
  const location = window.location.pathname;
  const id = location.split("/").pop();
  const product = products.find((item) => item.id === id) ?? products[0];
  const [quantity, setQuantity] = useState(1);
  return <PageFrame><section className="container py-8 lg:py-14"><button className="back-link" onClick={() => setLocation("/products")}><ArrowRight size={15} className="rotate-180" /> Back to collection</button><div className="mt-9 grid gap-12 lg:grid-cols-[1.05fr_.95fr] lg:items-start"><div className="product-detail-image"><img src={product.image} alt={product.name} /></div><div className="lg:sticky lg:top-28"><p className="eyebrow">{product.category} · {product.tone}</p><h1 className="page-heading mt-4 max-w-[520px]">{product.name}</h1><div className="mt-5 flex items-center gap-4"><span className="text-2xl font-medium">{money(product.price)}</span><span className="flex items-center gap-1 text-[13px] text-muted-foreground"><Star size={13} fill="currentColor" /> {product.rating} / 5</span></div><p className="mt-7 max-w-[500px] text-[15px] leading-7 text-muted-foreground">{product.description}</p><div className="mt-8 grid gap-3 border-y border-border py-5 text-[13px]"><div className="flex items-center gap-3"><Truck size={16} /><span>Complimentary delivery on orders over $150</span></div><div className="flex items-center gap-3"><RotateCcw size={16} /><span>30-day returns, no questions asked</span></div><div className="flex items-center gap-3"><ShieldCheck size={16} /><span>Two-year Atelier care promise</span></div></div><div className="mt-8 flex gap-3"><div className="quantity-stepper"><button onClick={() => setQuantity(Math.max(1, quantity - 1))}><Minus size={14} /></button><span>{quantity}</span><button onClick={() => setQuantity(quantity + 1)}><Plus size={14} /></button></div><Button className="premium-button flex-1" onClick={() => { for (let i = 0; i < quantity; i++) addToCart(product.id); }}>Add to bag <ShoppingBag size={16} /></Button><button className="icon-button border border-border" aria-label="Add to wishlist"><Heart size={18} /></button></div><div className="mt-9 grid gap-3 sm:grid-cols-2"><InfoBox icon={<LockKeyhole size={16} />} title="Secure checkout" text="Protected payment and privacy-first service." /><InfoBox icon={<MessageSquare size={16} />} title="Need a second opinion?" text="Ask the Atelier concierge." /></div></div></div></section></PageFrame>;
}

function InfoBox({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) { return <div className="info-box"><span className="text-[#a47a3b]">{icon}</span><div><p className="text-[13px] font-medium">{title}</p><p className="mt-1 text-[12px] leading-5 text-muted-foreground">{text}</p></div></div>; }

function AboutPage() { return <PageFrame><section className="container py-16 lg:py-24"><div className="grid gap-12 lg:grid-cols-[.8fr_1.2fr] lg:items-end"><div><p className="eyebrow">About Atelier</p><h1 className="page-heading mt-4">The beauty of<br /><em>enough.</em></h1></div><p className="body-lead max-w-[520px]">We make the things that stay. Objects with a point of view, a sense of place, and the patience to become part of your everyday.</p></div><div className="about-split mt-16"><div className="about-image"><img src={images.objects} alt="Dark stone and brass objects" /></div><div className="about-copy"><p className="eyebrow">Our point of view</p><h2 className="section-heading mt-4">Less, but better considered.</h2><p className="mt-6 text-[15px] leading-7 text-muted-foreground">Atelier began with a simple question: what would it look like to buy fewer things, and feel more connected to them? We work with small workshops, natural materials, and silhouettes that don’t ask to be replaced every season.</p><p className="mt-5 text-[15px] leading-7 text-muted-foreground">Every piece is designed in our studio and refined in conversation with the people who make it. The result is a collection that feels quiet at first, then becomes familiar.</p><div className="mt-9 grid grid-cols-2 gap-6 border-t border-border pt-6"><div><p className="stat-number">14</p><p className="mt-1 text-[12px] text-muted-foreground">small-run makers</p></div><div><p className="stat-number">01</p><p className="mt-1 text-[12px] text-muted-foreground">clear design language</p></div></div></div></div></section><section className="border-y border-border bg-secondary/40"><div className="container grid gap-8 py-16 md:grid-cols-3">{[["01", "Material honesty", "We choose materials for how they age, not how they photograph."], ["02", "Human scale", "Small runs let us listen, refine, and keep quality close."], ["03", "Long aftercare", "The relationship doesn’t end at checkout." ]].map(([num, title, text]) => <div key={num} className="border-t border-border pt-5"><span className="micro-label">{num}</span><h3 className="mt-9 font-serif text-2xl italic">{title}</h3><p className="mt-3 text-[14px] leading-6 text-muted-foreground">{text}</p></div>)}</div></section></PageFrame>; }

function SupportPage({ tickets, setTickets }: { tickets: Ticket[]; setTickets: React.Dispatch<React.SetStateAction<Ticket[]>> }) {
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const submit = (event: React.FormEvent) => { event.preventDefault(); if (!subject.trim() || !message.trim()) return; setTickets((current) => [{ id: `AT-${1050 + current.length}`, subject, category: "General support", status: "Open", date: "17 Sep 2026" }, ...current]); setSubject(""); setMessage(""); toast.success("Support ticket created", { description: "Our care team will reply within one business day." }); };
  return <PageFrame><section className="container py-14 lg:py-20"><div className="grid gap-12 lg:grid-cols-[.8fr_1.2fr]"><div><p className="eyebrow">Care, with a human touch</p><h1 className="page-heading mt-4">How can we<br /><em>help?</em></h1><p className="mt-6 max-w-[420px] text-[15px] leading-7 text-muted-foreground">Questions about an order, a material, or finding the right gift? Write to us and our team will take it from here.</p><div className="mt-10 grid gap-3"><button className="support-link" onClick={() => window.location.assign("/ai-concierge")}><span><Sparkles size={16} />Ask the AI concierge</span><ArrowUpRight size={15} /></button><button className="support-link"><span><Mail size={16} />care@atelierobjects.com</span><ArrowUpRight size={15} /></button><div className="support-link"><span><Clock3 size={16} />Mon–Fri · 09:00–18:00 CET</span></div></div></div><form onSubmit={submit} className="form-panel"><div className="flex items-center justify-between"><div><p className="eyebrow">Open a ticket</p><h2 className="mt-3 font-serif text-3xl">Tell us what’s on your mind.</h2></div><MessageSquare className="text-[#a47a3b]" /></div><label className="form-label mt-9">Subject<input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Question about sizing" required /></label><label className="form-label mt-5">How can we help?<Textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Give us a little context and we’ll do the rest." required className="min-h-[125px]" /></label><div className="mt-5 flex items-center justify-between gap-4"><p className="text-[12px] leading-5 text-muted-foreground">By submitting, you agree to receive a reply from our care team.</p><Button type="submit" className="premium-button">Send ticket <Send size={15} /></Button></div></form></div><div className="mt-20"><div className="flex items-end justify-between gap-4"><div><p className="eyebrow">Your support history</p><h2 className="section-heading mt-3">Recent conversations</h2></div><Badge variant="outline" className="rounded-full px-3 py-1">{tickets.length} tickets</Badge></div><div className="mt-8 overflow-x-auto border-y border-border"><table className="data-table"><thead><tr><th>Ticket</th><th>Subject</th><th>Status</th><th>Date</th></tr></thead><tbody>{tickets.map((ticket) => <tr key={ticket.id}><td className="font-mono text-[12px]">{ticket.id}</td><td><p className="font-medium">{ticket.subject}</p><p className="mt-1 text-[12px] text-muted-foreground">{ticket.category}</p></td><td><StatusBadge status={ticket.status} /></td><td className="text-muted-foreground">{ticket.date}</td></tr>)}</tbody></table></div></div></section></PageFrame>;
}

function StatusBadge({ status }: { status: Ticket["status"] }) { return <span className={`status-badge status-${status.toLowerCase().replace(" ", "-")}`}>{status === "Resolved" ? <CheckCircle2 size={13} /> : status === "In progress" ? <Clock3 size={13} /> : <Inbox size={13} />}{status}</span>; }

function ConciergePage() {
  const [messages, setMessages] = useState<Message[]>([{ role: "system", content: "You are the Atelier AI concierge. Be warm, concise, and knowledgeable about the collection." }, { role: "assistant", content: "Hello. I’m the Atelier concierge. Tell me what you’re looking for—an everyday carry, a considered gift, or perhaps a ritual for home—and I’ll point you in the right direction." }]);
  const [loading, setLoading] = useState(false);
  const onSendMessage = (content: string) => { setMessages((current) => [...current, { role: "user", content }]); setLoading(true); window.setTimeout(() => { const answer = content.toLowerCase().includes("gift") ? "For a considered gift, I’d begin with the **Lumen drop earrings** or the **Nadir incense set**. Both feel personal without requiring you to know someone’s exact size. Would you like something more tactile or more luminous?" : content.toLowerCase().includes("bag") || content.toLowerCase().includes("carry") ? "The **Mara sculptural tote** is the everyday hero: softly structured, full-grain leather, and roomy enough for a laptop without feeling like workwear. If you’re travelling, the **Alba travel case** is the more compact companion." : "That’s a lovely place to start. I’d suggest browsing the current edit by material and ritual, then I can help you narrow it down. What matters most: daily utility, gifting, or creating a calmer space?"; setMessages((current) => [...current, { role: "assistant", content: answer }]); setLoading(false); }, 850); };
  return <PageFrame><section className="container py-14 lg:py-20"><div className="mx-auto max-w-[900px]"><div className="flex flex-wrap items-end justify-between gap-6"><div><p className="eyebrow">Atelier intelligence</p><h1 className="page-heading mt-4">Meet your <em>concierge.</em></h1><p className="mt-5 max-w-[540px] text-[15px] leading-7 text-muted-foreground">A little context goes a long way. Ask about materials, gifting, care, or finding the right piece for your everyday.</p></div><div className="ai-status"><span className="ai-pulse" />Online · ready to help</div></div><div className="mt-10 overflow-hidden rounded-2xl border border-border bg-card shadow-[0_20px_80px_rgba(32,28,20,.08)]"><div className="flex items-center justify-between border-b border-border px-5 py-4"><div className="flex items-center gap-3"><div className="ai-avatar"><WandSparkles size={16} /></div><div><p className="text-[13px] font-semibold">Atelier concierge</p><p className="text-[11px] text-muted-foreground">Collection-aware support</p></div></div><button className="icon-button h-8 w-8"><Settings2 size={15} /></button></div><AIChatBox messages={messages} onSendMessage={onSendMessage} isLoading={loading} height="540px" placeholder="Ask about the collection..." suggestedPrompts={["Help me choose a gift", "Which bag works every day?", "How should I care for leather?"]} className="rounded-none border-0 shadow-none" /></div><div className="mt-5 flex flex-wrap gap-4 text-[12px] text-muted-foreground"><span className="flex items-center gap-2"><ShieldCheck size={14} /> No account required</span><span className="flex items-center gap-2"><LockKeyhole size={14} /> Private by design</span><span className="flex items-center gap-2"><CircleHelp size={14} /> Human support always available</span></div></div></section></PageFrame>;
}

function AuthPage({ onAuth }: { onAuth: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [, setLocation] = useLocation();
  const submit = (event: React.FormEvent) => { event.preventDefault(); onAuth(); toast.success(mode === "login" ? "Welcome back to Atelier" : "Your Atelier account is ready"); setLocation("/account"); };
  return <PageFrame><section className="container grid min-h-[720px] items-center gap-12 py-14 lg:grid-cols-[1fr_.85fr]"><div className="hidden overflow-hidden rounded-2xl bg-[#1c1c1a] lg:block"><div className="relative min-h-[610px]"><img src={images.editorial} alt="Atelier still life" className="absolute inset-0 h-full w-full object-cover opacity-70" /><div className="absolute inset-0 bg-gradient-to-t from-[#191918] via-transparent to-transparent" /><div className="absolute bottom-10 left-10 right-10 text-white"><p className="eyebrow text-[#d8bf98]">Atelier members</p><p className="mt-4 max-w-[360px] font-serif text-4xl leading-[1]">The pieces you choose should remember you.</p></div></div></div><div className="mx-auto w-full max-w-[430px]"><p className="eyebrow">{mode === "login" ? "Welcome back" : "Begin your edit"}</p><h1 className="mt-4 font-serif text-5xl tracking-[-.035em]">{mode === "login" ? "Sign in." : "Create an account."}</h1><p className="mt-5 text-[14px] leading-6 text-muted-foreground">{mode === "login" ? "Access saved pieces, order history, and your personal support conversations." : "Save your favourites, move faster at checkout, and make the collection yours."}</p><form onSubmit={submit} className="mt-9"><label className="form-label">Email address<input type="email" placeholder="you@example.com" required /></label><label className="form-label mt-4">Password<div className="relative"><input type="password" placeholder="••••••••" required /><LockKeyhole size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" /></div></label>{mode === "signup" && <label className="form-label mt-4">Your name<input placeholder="Avery Morgan" required /></label>}<Button type="submit" className="premium-button mt-7 w-full justify-center">{mode === "login" ? "Sign in to Atelier" : "Create my account"}<ArrowUpRight size={15} /></Button></form><div className="my-6 flex items-center gap-3 text-[11px] uppercase tracking-[.16em] text-muted-foreground"><span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" /></div><Button variant="outline" className="h-11 w-full rounded-full" onClick={() => startLogin()}>Continue with Manus <ArrowRight size={15} /></Button><p className="mt-7 text-center text-[13px] text-muted-foreground">{mode === "login" ? "New to Atelier?" : "Already have an account?"} <button className="font-medium text-foreground underline underline-offset-4" onClick={() => setMode(mode === "login" ? "signup" : "login")}>{mode === "login" ? "Create one" : "Sign in"}</button></p></div></section></PageFrame>;
}

function CartPage({ products, cart, removeFromCart, clearCart }: { products: Product[]; cart: string[]; removeFromCart: (id: string) => void; clearCart: () => void }) {
  const [, setLocation] = useLocation();
  const lines = Array.from(new Set(cart)).map((id) => ({ product: products.find((item) => item.id === id)!, quantity: cart.filter((item) => item === id).length })).filter((line) => line.product);
  const subtotal = lines.reduce((sum, line) => sum + line.product.price * line.quantity, 0);
  return <PageFrame><section className="container py-14 lg:py-20"><div className="flex flex-wrap items-end justify-between gap-5"><div><p className="eyebrow">Your edit</p><h1 className="page-heading mt-4">The <em>bag.</em></h1></div>{cart.length > 0 && <button className="text-link text-[12px]" onClick={clearCart}>Clear bag <Trash2 size={14} /></button>}</div>{cart.length === 0 ? <div className="empty-state mt-12"><ShoppingBag size={26} /><h2 className="font-serif text-2xl">Your bag is waiting.</h2><p className="text-[14px] text-muted-foreground">Find something considered for the everyday.</p><Button className="premium-button" onClick={() => setLocation("/products")}>Explore the collection <ArrowRight size={15} /></Button></div> : <div className="mt-12 grid gap-10 lg:grid-cols-[1.2fr_.8fr]"><div className="divide-y divide-border border-y border-border">{lines.map(({ product, quantity }) => <div key={product.id} className="flex gap-5 py-5"><img src={product.image} alt={product.name} className="h-28 w-24 rounded-lg object-cover" /><div className="flex flex-1 flex-col justify-between gap-3"><div className="flex justify-between gap-4"><div><p className="font-medium">{product.name}</p><p className="mt-1 text-[13px] text-muted-foreground">{product.category} · {product.tone}</p></div><p className="font-medium">{money(product.price * quantity)}</p></div><div className="flex items-center justify-between"><span className="text-[12px] text-muted-foreground">Qty {quantity}</span><button className="text-link text-[12px]" onClick={() => removeFromCart(product.id)}>Remove <X size={13} /></button></div></div></div>)}</div><div className="summary-panel h-fit"><p className="eyebrow">Order summary</p><div className="mt-6 space-y-4 text-[14px]"><div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span>{money(subtotal)}</span></div><div className="flex justify-between"><span className="text-muted-foreground">Delivery</span><span>{subtotal >= 150 ? "Complimentary" : "$12"}</span></div><div className="border-t border-border pt-4 text-base font-medium"><div className="flex justify-between"><span>Total</span><span>{money(subtotal >= 150 ? subtotal : subtotal + 12)}</span></div></div></div><Button className="premium-button mt-8 w-full justify-center" onClick={() => toast.success("Checkout preview ready", { description: "Connect a payment provider to complete purchase." })}>Continue to checkout <ArrowUpRight size={15} /></Button><div className="mt-6 flex items-start gap-3 border-t border-border pt-5 text-[12px] leading-5 text-muted-foreground"><ShieldCheck size={16} className="mt-0.5 shrink-0" /> Your payment is protected by Atelier’s secure checkout.</div></div></div>}</section></PageFrame>;
}

function AccountPage({ demoUser, setDemoUser }: { demoUser: boolean; setDemoUser: (value: boolean) => void }) {
  const [, setLocation] = useLocation();
  if (!demoUser) return <PageFrame><section className="container flex min-h-[620px] items-center justify-center py-16"><div className="max-w-[420px] text-center"><div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-secondary"><UserRound size={24} /></div><p className="eyebrow mt-8">Your Atelier account</p><h1 className="mt-4 font-serif text-4xl">A place for your edit.</h1><p className="mt-4 text-[14px] leading-6 text-muted-foreground">Sign in to view orders, saved pieces, and support conversations.</p><Button className="premium-button mt-8" onClick={() => setLocation("/auth")}>Sign in or create an account <ArrowUpRight size={15} /></Button></div></section></PageFrame>;
  return <PageFrame><section className="container py-14 lg:py-20"><div className="flex flex-wrap items-end justify-between gap-6"><div><p className="eyebrow">Good morning, Avery</p><h1 className="page-heading mt-4">Your <em>Atelier.</em></h1></div><button className="text-link text-[12px]" onClick={() => { setDemoUser(false); toast("Signed out"); }}>Sign out <LogOut size={14} /></button></div><div className="mt-12 grid gap-5 sm:grid-cols-3"><AccountMetric label="Open order" value="#AT-2084" detail="Arriving 21 Sep" icon={<Truck size={17} />} /><AccountMetric label="Saved pieces" value="08" detail="Ready when you are" icon={<Heart size={17} />} /><AccountMetric label="Support" value="01" detail="Conversation active" icon={<MessageSquare size={17} />} /></div><div className="mt-14 grid gap-10 lg:grid-cols-[1.15fr_.85fr]"><div><div className="flex items-center justify-between"><div><p className="eyebrow">Recent order</p><h2 className="section-heading mt-3">A slower kind of delivery.</h2></div><button className="text-link text-[12px]">View all <ArrowRight size={14} /></button></div><div className="order-card mt-7"><div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5"><div><p className="font-mono text-[12px]">ORDER AT-2084</p><p className="mt-2 text-[13px] text-muted-foreground">Placed 16 Sep 2026</p></div><span className="status-badge status-in-progress"><Truck size={13} />In transit</span></div><div className="mt-5 flex gap-4"><img src={images.travel} alt="Mara sculptural tote" className="h-20 w-16 rounded-lg object-cover" /><div><p className="font-medium">Mara sculptural tote</p><p className="mt-1 text-[13px] text-muted-foreground">Sand · Qty 1</p><p className="mt-3 text-[12px] text-muted-foreground">Your order is on its way from our Paris studio.</p></div></div></div></div><div><div className="flex items-center justify-between"><div><p className="eyebrow">Your details</p><h2 className="section-heading mt-3">A little about you.</h2></div><button className="icon-button" onClick={() => setLocation("/account/profile")}><Pencil size={15} /></button></div><div className="profile-card mt-7"><div className="avatar-large">AM</div><div className="mt-5"><p className="font-medium">Avery Morgan</p><p className="mt-1 text-[13px] text-muted-foreground">avery.morgan@example.com</p></div><div className="mt-6 grid gap-3 border-t border-border pt-5 text-[13px]"><span className="flex items-center gap-3"><MapPin size={15} className="text-muted-foreground" />Paris, France</span><span className="flex items-center gap-3"><CreditCard size={15} className="text-muted-foreground" />Visa ending in 4820</span></div></div></div></div></section></PageFrame>;
}

function AccountMetric({ label, value, detail, icon }: { label: string; value: string; detail: string; icon: React.ReactNode }) { return <div className="metric-card"><div className="flex items-center justify-between text-muted-foreground"><span className="eyebrow">{label}</span>{icon}</div><p className="mt-7 font-serif text-3xl">{value}</p><p className="mt-1 text-[12px] text-muted-foreground">{detail}</p></div>; }

function ProfilePage({ setDemoUser }: { demoUser: boolean; setDemoUser: (value: boolean) => void }) { const [, setLocation] = useLocation(); const [name, setName] = useState("Avery Morgan"); const [email, setEmail] = useState("avery.morgan@example.com"); const save = (event: React.FormEvent) => { event.preventDefault(); toast.success("Profile updated"); setLocation("/account"); }; return <PageFrame><section className="container max-w-[900px] py-14 lg:py-20"><button className="back-link" onClick={() => setLocation("/account")}><ArrowRight size={15} className="rotate-180" /> Back to account</button><div className="mt-10 grid gap-12 lg:grid-cols-[.7fr_1.3fr]"><div><p className="eyebrow">Account settings</p><h1 className="page-heading mt-4">Edit your <em>profile.</em></h1><p className="mt-5 text-[14px] leading-6 text-muted-foreground">Keep your details current so the Atelier team can make every delivery feel considered.</p></div><form onSubmit={save} className="form-panel"><div className="avatar-large">AM</div><label className="form-label mt-8">Full name<input value={name} onChange={(e) => setName(e.target.value)} /></label><label className="form-label mt-4">Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label><label className="form-label mt-4">City<input defaultValue="Paris, France" /></label><div className="mt-8 flex justify-between gap-3"><Button type="button" variant="outline" onClick={() => setLocation("/account")}>Cancel</Button><Button type="submit" className="premium-button">Save changes <Check size={15} /></Button></div></form></div></section></PageFrame>; }

function AdminPage({ products, setProducts, tickets, setTickets }: { products: Product[]; setProducts: React.Dispatch<React.SetStateAction<Product[]>>; tickets: Ticket[]; setTickets: React.Dispatch<React.SetStateAction<Ticket[]>> }) {
  const [active, setActive] = useState<"overview" | "products" | "tickets">("overview");
  const [editing, setEditing] = useState<Product | null>(null);
  const [newName, setNewName] = useState("");
  const stats = [{ label: "Gross sales", value: "$24,860", change: "+18.4%", icon: <BarChart3 size={16} /> }, { label: "Orders", value: "184", change: "+12.2%", icon: <Package size={16} /> }, { label: "Open tickets", value: String(tickets.filter((ticket) => ticket.status !== "Resolved").length).padStart(2, "0"), change: "-8.1%", icon: <Inbox size={16} /> }, { label: "Conversion", value: "4.8%", change: "+0.6%", icon: <ArrowUpRight size={16} /> }];
  const addProduct = () => { if (!newName.trim()) return; setProducts((current) => [{ id: `custom-${Date.now()}`, name: newName, category: "New edit", price: 120, description: "A newly added Atelier object.", image: images.editorial, tone: "New", stock: 12, rating: 4.8 }, ...current]); setNewName(""); toast.success("Product created"); };
  const updateStatus = (id: string, status: Ticket["status"]) => { setTickets((current) => current.map((ticket) => ticket.id === id ? { ...ticket, status } : ticket)); toast.success(`Ticket ${id} updated`); };
  return <PageFrame><section className="container py-8 lg:py-12"><div className="admin-header"><div><p className="eyebrow">Atelier operations</p><h1 className="page-heading mt-3">The <em>back office.</em></h1><p className="mt-4 text-[14px] text-muted-foreground">Manage the collection, care conversations, and the health of the studio.</p></div><div className="admin-user"><div className="avatar-small">AD</div><div><p className="text-[13px] font-medium">Admin workspace</p><p className="text-[11px] text-muted-foreground">Live preview mode</p></div></div></div><div className="admin-shell mt-10"><aside className="admin-sidebar">{[["overview", LayoutDashboard, "Overview"], ["products", Tag, "Products"], ["tickets", Inbox, "Tickets"]].map(([key, Icon, label]) => <button key={key as string} className={`admin-nav ${active === key ? "admin-nav-active" : ""}`} onClick={() => setActive(key as typeof active)}><Icon size={16} />{label as string}{key === "tickets" && <span className="ml-auto rounded-full bg-[#d8bf98] px-2 py-0.5 text-[10px] text-[#171717]">{tickets.filter((ticket) => ticket.status !== "Resolved").length}</span>}</button>)}<div className="mt-auto border-t border-border pt-5"><button className="admin-nav"><Settings2 size={16} />Settings</button><button className="admin-nav"><LogOut size={16} />Sign out</button></div></aside><div className="admin-content">{active === "overview" && <><div className="admin-stats">{stats.map((stat) => <div key={stat.label} className="admin-stat"><div className="flex items-center justify-between text-muted-foreground"><span className="eyebrow">{stat.label}</span>{stat.icon}</div><p className="mt-5 font-serif text-3xl">{stat.value}</p><p className="mt-2 text-[12px] text-[#69866c]">{stat.change} <span className="text-muted-foreground">vs last month</span></p></div>)}</div><div className="mt-8 grid gap-8 lg:grid-cols-[1.1fr_.9fr]"><div><div className="flex items-center justify-between"><div><p className="eyebrow">Collection pulse</p><h2 className="mt-2 font-serif text-2xl">Best sellers this month</h2></div><button className="text-link text-[12px]" onClick={() => setActive("products")}>Manage products <ArrowRight size={14} /></button></div><div className="mt-5 divide-y divide-border border-y border-border">{products.slice(0, 4).map((product) => <div key={product.id} className="flex items-center gap-4 py-4"><img src={product.image} alt="" className="h-12 w-12 rounded-md object-cover" /><div className="min-w-0 flex-1"><p className="truncate text-[13px] font-medium">{product.name}</p><p className="mt-1 text-[11px] text-muted-foreground">{product.stock} in stock · {product.category}</p></div><span className="font-medium">{money(product.price)}</span></div>)}</div></div><div className="admin-callout"><div className="ai-avatar"><Sparkles size={16} /></div><p className="eyebrow mt-5 text-[#d8bf98]">Care team note</p><h3 className="mt-3 font-serif text-2xl text-white">Keep the reply personal.</h3><p className="mt-3 text-[13px] leading-6 text-white/60">Three customers are waiting on product care advice. The AI concierge can suggest a first draft, but a human should always have the last word.</p><button className="mt-7 flex items-center gap-2 text-[12px] font-medium text-[#d8bf98]" onClick={() => setActive("tickets")}>Review conversations <ArrowRight size={14} /></button></div></div></>}{active === "products" && <div><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">Catalog management</p><h2 className="mt-2 font-serif text-3xl">Products</h2></div><div className="flex gap-2"><Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New product name" className="h-10 w-[190px]" /><Button className="premium-button h-10" onClick={addProduct}><Plus size={15} />Add product</Button></div></div><div className="mt-8 overflow-x-auto border-y border-border"><table className="data-table"><thead><tr><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Action</th></tr></thead><tbody>{products.map((product) => <tr key={product.id}><td><div className="flex items-center gap-3"><img src={product.image} alt="" className="h-10 w-10 rounded-md object-cover" /><span className="font-medium">{product.name}</span></div></td><td className="text-muted-foreground">{product.category}</td><td>{money(product.price)}</td><td><span className={product.stock < 12 ? "text-[#b2764a]" : "text-[#69866c]"}>{product.stock} units</span></td><td><div className="flex gap-1"><button className="icon-button h-8 w-8" onClick={() => setEditing(product)}><Pencil size={14} /></button><button className="icon-button h-8 w-8 text-destructive" onClick={() => { setProducts((current) => current.filter((item) => item.id !== product.id)); toast.success("Product removed"); }}><Trash2 size={14} /></button></div></td></tr>)}</tbody></table></div></div>}{active === "tickets" && <div><div><p className="eyebrow">Care operations</p><h2 className="mt-2 font-serif text-3xl">Support tickets</h2></div><div className="mt-8 overflow-x-auto border-y border-border"><table className="data-table"><thead><tr><th>Ticket</th><th>Subject</th><th>Status</th><th>Update</th></tr></thead><tbody>{tickets.map((ticket) => <tr key={ticket.id}><td className="font-mono text-[12px]">{ticket.id}</td><td><p className="font-medium">{ticket.subject}</p><p className="mt-1 text-[11px] text-muted-foreground">{ticket.category} · {ticket.date}</p></td><td><StatusBadge status={ticket.status} /></td><td><select className="admin-select" value={ticket.status} onChange={(e) => updateStatus(ticket.id, e.target.value as Ticket["status"])}><option>Open</option><option>In progress</option><option>Resolved</option></select></td></tr>)}</tbody></table></div></div>}</div></div></section>{editing && <div className="modal-backdrop" onClick={() => setEditing(null)}><motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="modal-card" onClick={(event) => event.stopPropagation()}><div className="flex items-start justify-between"><div><p className="eyebrow">Edit catalog item</p><h2 className="mt-2 font-serif text-2xl">{editing.name}</h2></div><button className="icon-button h-8 w-8" onClick={() => setEditing(null)}><X size={16} /></button></div><label className="form-label mt-7">Product name<input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></label><label className="form-label mt-4">Price<input type="number" value={editing.price} onChange={(e) => setEditing({ ...editing, price: Number(e.target.value) })} /></label><label className="form-label mt-4">Stock<input type="number" value={editing.stock} onChange={(e) => setEditing({ ...editing, stock: Number(e.target.value) })} /></label><div className="mt-8 flex justify-end gap-3"><Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button className="premium-button" onClick={() => { setProducts((current) => current.map((item) => item.id === editing.id ? editing : item)); setEditing(null); toast.success("Product updated"); }}>Save product <Check size={15} /></Button></div></motion.div></div>}</PageFrame>;
}

function PageFrame({ children, className = "" }: { children: React.ReactNode; className?: string }) { return <motion.main initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: .25 }} className={className}>{children}</motion.main>; }

function SiteFooter() { const [, setLocation] = useLocation(); return <footer className="border-t border-border bg-secondary/25"><div className="container grid gap-10 py-14 lg:grid-cols-[1.2fr_.8fr_.8fr_.8fr]"><div><div className="flex items-center gap-3"><span className="brand-mark">A</span><span className="text-[13px] font-semibold uppercase tracking-[.28em]">Atelier</span></div><p className="mt-5 max-w-[280px] text-[13px] leading-6 text-muted-foreground">Objects with intention for the rituals that shape your day.</p></div><div><p className="footer-heading">Explore</p><div className="mt-4 grid gap-3 text-[13px] text-muted-foreground"><button className="footer-link" onClick={() => setLocation("/products")}>Collection</button><button className="footer-link" onClick={() => setLocation("/about")}>Our story</button><button className="footer-link" onClick={() => setLocation("/ai-concierge")}>AI concierge</button></div></div><div><p className="footer-heading">Care</p><div className="mt-4 grid gap-3 text-[13px] text-muted-foreground"><button className="footer-link" onClick={() => setLocation("/support")}>Support center</button><button className="footer-link">Delivery & returns</button><button className="footer-link">Material care</button></div></div><div><p className="footer-heading">Stay close</p><p className="mt-4 text-[13px] leading-6 text-muted-foreground">A quiet note on new objects, studio stories, and good things worth keeping.</p><div className="mt-4 flex gap-2"><input className="footer-input" placeholder="Email address" /><button className="footer-submit" onClick={() => toast.success("You’re on the list")}>→</button></div></div></div><div className="container flex flex-wrap justify-between gap-3 border-t border-border py-5 text-[11px] text-muted-foreground"><span>© 2026 Atelier Objects</span><span>Designed with intention · Paris / Everywhere</span><button className="footer-link" onClick={() => setLocation("/admin")}>Admin preview</button></div></footer>; }

function NotFoundPage() { const [, setLocation] = useLocation(); return <PageFrame><section className="container flex min-h-[620px] items-center justify-center text-center"><div><p className="eyebrow">404 · Not found</p><h1 className="mt-4 font-serif text-5xl">This page took a different path.</h1><button className="text-link mt-8" onClick={() => setLocation("/")}>Return home <ArrowRight size={15} /></button></div></section></PageFrame>; }

export default App;

// Keep the unused imports below from causing a less useful lint warning in strict editors when the app is extended.
void ArrowDownRight;
void FilePenLine;
void UserCog;
void Bot;
void BarChart3;
void Minus;
void Plus;
void Mail;
void CheckCircle2;
void ShieldCheck;
void Star;
void Tag;
void CreditCard;
void LayoutDashboard;
void MessageSquare;
void UserRound;
void MapPin;
void Search;
void SlidersHorizontal;
void CircleHelp;
void Clock3;
void Package;
void Truck;
void RotateCcw;
void LockKeyhole;
void WandSparkles;
void Sparkles;
void Inbox;
void Settings2;
void ShoppingBag;
void Heart;
void Pencil;
void Trash2;
void X;
void ChevronDown;
void ChevronRight;
void Moon;
void Sun;
void Send;
void LogOut;
void ArrowUpRight;
void ArrowRight;
void Menu;
