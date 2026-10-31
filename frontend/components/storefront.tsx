"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ArrowUpRight, AudioLines, Check, ChevronDown, ChevronRight, CircleUserRound, Headphones, Heart, Menu, MessageCircle, Mic, Minus, Plus, Search, ShieldCheck, ShoppingBag, SlidersHorizontal, Sparkles, Truck, X, Zap } from "lucide-react";
import LiveVoice from "@/components/live-voice";

type Product = { id: string; name: string; category: string; brand: string; tagline: string; description: string; price: number; compare_at: number | null; stock: number; rating: number; review_count: number; image_key: string; color: string; specs: Record<string,string>; featured: boolean };
type CartRow = { product: Product; quantity: number };
type Message = { role: "user" | "assistant"; text: string };
type OrderItem = { product_id: string; product_name: string; quantity: number; unit_price: number };
type CustomerOrder = { id: string; order_reference: string; status: string; payment_status: string; subtotal: number; shipping: number; total: number; currency: string; created_at: string; items: OrderItem[] };
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const categories = ["All products", "Audio", "Wearables", "Smart home", "Accessories"];
const currency = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);

function ProductArt({ product, large = false }: { product: Product; large?: boolean }) {
  const className = `product-art art-${product.image_key}${large ? " art-large" : ""}`;
  return <div className={className} style={{ "--art": product.color } as React.CSSProperties} aria-hidden="true">
    <div className="art-orbit" />
    {product.image_key === "buds" && <div className="buds"><i/><i/><b/><b/></div>}
    {product.image_key === "watch" && <div className="watch"><i/><b>10:08</b><small>MON · 21</small></div>}
    {product.image_key === "speaker" && <div className="speaker"><i/><i/><i/><b/></div>}
    {product.image_key === "projector" && <div className="projector"><i/><b/></div>}
    {product.image_key === "keyboard" && <div className="keyboard">{Array.from({length: 18},(_,i)=><i key={i}/>)}</div>}
    {product.image_key === "mouse" && <div className="mouse"><i/></div>}
    {product.image_key === "camera" && <div className="camera"><i/><b/></div>}
    {product.image_key === "powerbank" && <div className="powerbank"><i>20K</i><b/></div>}
    {product.image_key === "charger" && <div className="charger"><i/><b/></div>}
    {product.image_key === "ring" && <div className="ring"><i/></div>}
    {product.image_key === "lamp" && <div className="lamp"><i/><b/><em/></div>}
    {product.image_key === "headphones" && <div className="headphones"><i/><b/><em/></div>}
  </div>;
}

function IconButton({ children, label, onClick, active = false }: { children: React.ReactNode; label: string; onClick: () => void; active?: boolean }) {
  return <button className={`icon-button${active ? " is-active" : ""}`} aria-label={label} title={label} onClick={onClick}>{children}</button>;
}

export default function Storefront() {
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All products");
  const [sort, setSort] = useState("featured");
  const [cart, setCart] = useState<CartRow[]>([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [compare, setCompare] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [detailProduct, setDetailProduct] = useState<Product | null>(null);
  const [customer, setCustomer] = useState<{ email: string; authenticated: boolean } | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [authMode, setAuthMode] = useState("dev");
  const [profileOpen, setProfileOpen] = useState(false);
  const [customerOrders, setCustomerOrders] = useState<CustomerOrder[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [ordersLoaded, setOrdersLoaded] = useState(false);
  const [ordersError, setOrdersError] = useState("");
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [orderNotice, setOrderNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([{ role: "assistant", text: "Hi, I’m HarizonAI. Looking for something specific, or have a question about a product?" }]);
  const [chatText, setChatText] = useState("");
  const [listening, setListening] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [toast, setToast] = useState("");

  const load = async () => {
    try {
      const response = await fetch(`${API}/api/products?q=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}&sort=${sort}`);
      if (response.ok) setProducts(await response.json());
    } catch { setToast("Could not connect to the local store API."); }
    setLoading(false);
  };
  useEffect(() => { void load(); }, [query, category, sort]);
  useEffect(() => { void fetch(`${API}/api/auth/config`).then(r => r.json()).then(cfg => setAuthMode(cfg.mode)).catch(() => setAuthMode("dev")); }, []);
  useEffect(() => {
    try { const saved = localStorage.getItem("harizon-cart"); if (saved) setCart(JSON.parse(saved)); } catch { /* Ignore invalid local cart data. */ }
    fetch(`${API}/api/auth/me`, { credentials: "include" }).then(r => r.json()).then(v => { setCustomer({ email: v.email || "", authenticated: !!v.authenticated }); setCustomerName(v.name || ""); }).catch(() => { setCustomer({email:"",authenticated:false}); setCustomerName(""); });
  }, []);
  useEffect(() => { localStorage.setItem("harizon-cart", JSON.stringify(cart)); }, [cart]);
  useEffect(() => { if (toast) { const id = setTimeout(() => setToast(""), 2600); return () => clearTimeout(id); } }, [toast]);

  const totalCount = cart.reduce((sum, row) => sum + row.quantity, 0);
  const subtotal = cart.reduce((sum, row) => sum + row.product.price * row.quantity, 0);
  const compareProducts = useMemo(() => products.filter(p => compare.includes(p.id)), [products, compare]);
  const addToCart = (product: Product) => { setCart(rows => { const found = rows.find(r => r.product.id === product.id); return found ? rows.map(r => r.product.id === product.id ? { ...r, quantity: Math.min(10, r.quantity + 1) } : r) : [...rows, {product, quantity: 1}]; }); setToast(`${product.name} added to bag`); };
  const changeQuantity = (id: string, delta: number) => setCart(rows => rows.map(r => r.product.id === id ? {...r, quantity: r.quantity + delta} : r).filter(r => r.quantity > 0));
  const toggleCompare = (product: Product) => setCompare(ids => ids.includes(product.id) ? ids.filter(x => x !== product.id) : ids.length >= 3 ? (setToast("Compare up to 3 products at a time"), ids) : [...ids, product.id]);

  const signIn = async () => {
    const cfg = await fetch(`${API}/api/auth/config`).then(r => r.json()).catch(() => ({mode:"dev"}));
    if (cfg.mode === "auth0") { window.location.href = `${API}/api/auth/login`; return; }
    const res = await fetch(`${API}/api/auth/dev-login`, { method: "POST", credentials: "include" });
    if (res.ok) { const me = await res.json(); setCustomer({email:me.email,authenticated:true}); setCustomerName(me.name || "Local Shopper"); setProfileOpen(false); setToast("Signed in with local development account"); }
    else setToast("Sign in is not available. Check the API configuration.");
  };
  const signOut = async () => { await fetch(`${API}/api/auth/logout`, {method:"POST",credentials:"include"}); setCustomer({email:"",authenticated:false}); setCustomerName(""); setCustomerOrders([]); setOrdersLoaded(false); setProfileOpen(false); };
  const loadCustomerOrders = async () => {
    setOrdersLoading(true); setOrdersError("");
    try {
      const response = await fetch(`${API}/api/orders`, {credentials:"include"});
      if (!response.ok) throw new Error(response.status === 401 ? "Please sign in again to view your orders." : "We couldn't load your orders right now.");
      setCustomerOrders(await response.json()); setOrdersLoaded(true);
    } catch (error) { setOrdersError(error instanceof Error ? error.message : "We couldn't load your orders right now."); }
    finally { setOrdersLoading(false); }
  };

  const sendMessage = async (text = chatText) => {
    const message = text.trim(); if (!message || chatBusy) return;
    setChatText(""); setMessages(rows => [...rows, {role:"user",text:message}]); setChatBusy(true);
    try {
      const res = await fetch(`${API}/api/assistant/chat`, {method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({message})});
      const data = await res.json(); setMessages(rows => [...rows, {role:"assistant",text:data.reply || "I couldn’t find an answer just now."}]);
      if ("speechSynthesis" in window) { const utterance = new SpeechSynthesisUtterance(data.reply); utterance.lang="en-IN"; window.speechSynthesis.cancel(); window.speechSynthesis.speak(utterance); }
    } catch { setMessages(rows => [...rows,{role:"assistant",text:"I’m having trouble connecting. You can still browse the store, or try again in a moment."}]); }
    finally { setChatBusy(false); }
  };
  const startVoice = () => {
    const w = window as unknown as { SpeechRecognition?: new () => any; webkitSpeechRecognition?: new () => any };
    const Engine = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Engine) { setToast("Voice input is not available in this browser. Try Chrome or type your question."); setAssistantOpen(true); return; }
    const recognition = new Engine(); recognition.lang = "en-IN"; recognition.interimResults = false; recognition.maxAlternatives = 1;
    recognition.onstart = () => { setListening(true); setAssistantOpen(true); };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => { setListening(false); setToast("Microphone input stopped. Please try again or type your question."); };
    recognition.onresult = (event: any) => { const heard = event.results?.[0]?.[0]?.transcript; if (heard) void sendMessage(heard); };
    recognition.start();
  };

  const submitCheckout = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!customer?.authenticated) { setCheckoutOpen(false); setProfileOpen(true); setToast("Sign in first to place an order"); return; }
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const response = await fetch(`${API}/api/checkout/orders`, {method:"POST",credentials:"include",headers:{"Content-Type":"application/json","Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({items:cart.map(row=>({product_id:row.product.id,quantity:row.quantity})),shipping_address:{full_name:values.full_name,line1:values.line1,line2:values.line2,city:values.city,state:values.state,postal_code:values.postal_code}})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not create order");
      if (result.payment.mode === "mock") {
        const paid = await fetch(`${API}/api/payments/mock/complete/${result.order.id}`,{method:"POST",credentials:"include"});
        if (!paid.ok) throw new Error("Order created, but local payment simulation failed");
      } else if (result.payment.mode === "razorpay") {
        await new Promise<void>((resolve,reject)=>{
          const script = document.createElement("script"); script.src="https://checkout.razorpay.com/v1/checkout.js";
          script.onload = () => {
            const Razorpay = (window as unknown as {Razorpay:new(o:Record<string,unknown>)=>{open:()=>void}}).Razorpay;
            const checkout = new Razorpay({key:result.payment.checkout_key,amount:Math.round(result.order.total*100),currency:"INR",name:"HARIZON",description:`Order ${result.order.id}`,order_id:result.payment.provider_order_id,prefill:{email:customer.email},handler:async (r:Record<string,string>)=>{const v=await fetch(`${API}/api/payments/verify`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({order_id:result.order.id,payment_id:r.razorpay_payment_id,signature:r.razorpay_signature})});v.ok?resolve():reject(new Error("Payment could not be verified"));},modal:{ondismiss:()=>reject(new Error("Checkout was closed"))}}); checkout.open();
          }; script.onerror=()=>reject(new Error("Could not load Razorpay checkout")); document.body.appendChild(script);
        });
      }
      setCart([]); setCheckoutOpen(false); setCartOpen(false); setOrderNotice(result.order.order_reference || result.order.id); setToast("Order placed — thank you!");
    } catch (error) { setToast(error instanceof Error ? error.message : "Checkout failed"); }
  };

  const createSupportTicket = async () => {
    if (!customer?.authenticated) { setToast("Please sign in before opening a support ticket"); return; }
    const confirmed = window.confirm("Create a support ticket? Your message will be shared with our support team.");
    if (!confirmed) return;
    const summary = messages.slice(-4).map(m => `${m.role}: ${m.text}`).join("\n").slice(0,1600);
    const response = await fetch(`${API}/api/support/tickets`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true,subject:"Shopping assistant handoff",summary})});
    const data=await response.json();
    if (response.ok) setMessages(rows=>[...rows,{role:"assistant",text:`A support ticket is created. Your reference is ${data.reference}.`}]);
    else setToast(data.detail || "Could not create a ticket");
  };

  return <main>
    <div className="announcement"><span>Complimentary delivery on orders over ₹5,000</span><span className="announcement-right">Designed for everyday. Made to stay. <ArrowUpRight size={13}/></span></div>
    <header className="site-header">
      <button className="mobile-menu icon-button" aria-label="Open menu"><Menu size={20}/></button>
      <a className="wordmark" href="#top"><span className="brand-mark">H<span>·</span></span><span>HARIZON</span></a>
      <nav className="main-nav"><a href="#shop">Shop all</a><a href="#shop" onClick={()=>setCategory("Audio")}>Audio</a><a href="#shop" onClick={()=>setCategory("Smart home")}>Smart home</a><a href="#story">Our point of view</a></nav>
      <div className="header-actions"><button className="search-toggle" onClick={()=>document.getElementById("search")?.focus()} aria-label="Search"><Search size={19}/><span>Search</span></button><button className="account-button" onClick={()=>setProfileOpen(true)} aria-label={customer?.authenticated ? `Account for ${customerName || customer.email}` : "Account"} title={customer?.authenticated ? customer.email : "Account"}><CircleUserRound size={19}/><span>{customer?.authenticated ? (customerName || customer.email.split("@")[0]) : "Account"}</span></button><IconButton label={`Shopping bag, ${totalCount} items`} onClick={()=>setCartOpen(true)}><ShoppingBag size={20}/>{totalCount>0&&<i className="bag-count">{totalCount}</i>}</IconButton></div>
    </header>

    {orderNotice && <div className="order-banner"><Check size={18}/><span>Order placed successfully · <strong>{orderNotice}</strong></span><button onClick={()=>setOrderNotice("")} aria-label="Dismiss"><X size={16}/></button></div>}

    <section className="hero" id="top">
      <div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line"/>TECH THAT FEELS LIKE YOU</div><h1>Make room for<br/><em>better</em> everyday.</h1><p>Thoughtfully chosen electronics and smart essentials that make the everyday feel a little more extraordinary.</p><div className="hero-actions"><a href="#shop" className="button button-dark">Explore the collection <ArrowRight size={16}/></a><button className="voice-intro" onClick={startVoice}><span className="voice-icon"><AudioLines size={18}/></span><span>Ask HarizonAI for a recommendation</span><ArrowUpRight size={14}/></button></div><div className="hero-note"><span className="note-avatars"><i>A</i><i>J</i><i>M</i></span><span><b>Considered by people, for people.</b><br/>A more human way to find what fits.</span></div></div>
      <div className="hero-visual"><div className="hero-image">
        <div className="hero-sun"/><div className="hero-plant plant-one"><i/><b/><em/></div><div className="hero-plant plant-two"><i/><b/><em/></div>
        <div className="hero-product hero-headphone"><div className="headphones"><i/><b/><em/></div></div><div className="hero-product hero-watch"><div className="watch"><i/><b>10:08</b><small>MON · 21</small></div></div><div className="hero-product hero-speaker"><div className="speaker"><i/><i/><i/><b/></div></div>
        <div className="hero-caption"><span>01 / EVERYDAY, ELEVATED</span><span>QUIETLY CAPABLE. BEAUTIFULLY MADE.</span></div><div className="hero-floating"><Sparkles size={15}/><span>Small things,<br/>thoughtfully done.</span></div>
      </div><div className="hero-side-label">THE HARIZON EDIT — NO. 01</div></div>
    </section>

    <section className="benefits"><div><span className="benefit-icon"><Truck size={18}/></span><span><b>Delivery on us</b><small>On orders over ₹5,000</small></span></div><div><span className="benefit-icon"><ShieldCheck size={18}/></span><span><b>Thoughtful warranty</b><small>1-year cover, always</small></span></div><div><span className="benefit-icon"><Heart size={18}/></span><span><b>Made to be kept</b><small>Chosen for everyday use</small></span></div><div><span className="benefit-icon"><Headphones size={18}/></span><span><b>Real human help</b><small>Here when you need us</small></span></div></section>

    <section className="shop-section" id="shop">
      <div className="section-heading"><div><div className="eyebrow"><span className="eyebrow-line"/>A SMALLER, BETTER EDIT</div><h2>Good things,<br className="mobile-break"/> <em>well chosen.</em></h2></div><p>Technology worth making space for.<br/>Explore the pieces that earn their place.</p></div>
      <div className="shop-toolbar"><div className="category-tabs" role="tablist" aria-label="Product category">{categories.map(item=><button key={item} role="tab" aria-selected={category===item} className={category===item?"selected":""} onClick={()=>setCategory(item)}>{item}</button>)}</div><div className="shop-tools"><label className="search-field"><Search size={17}/><input id="search" aria-label="Search products" placeholder="Find something good…" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button aria-label="Clear search" onClick={()=>setQuery("")}><X size={14}/></button>}</label><label className="sort-select"><SlidersHorizontal size={16}/><select value={sort} aria-label="Sort products" onChange={e=>setSort(e.target.value)}><option value="featured">Featured</option><option value="top-rated">Top rated</option><option value="price-low">Price: low to high</option><option value="price-high">Price: high to low</option></select><ChevronDown size={14}/></label></div></div>
      <div className="product-count"><span>{loading?"Finding your next favourite…":`${products.length} considered essentials`}</span><span>INR · TAXES INCLUDED</span></div>
      <div className="product-grid">{products.map((product,index)=><article className="product-card" key={product.id}>
        <div className="product-image" style={{background:product.color}}><ProductArt product={product}/><span className={`product-badge ${index===0?"badge-dark":""}`}>{index===0?"THE HARIZON PICK":product.category.toUpperCase()}</span><button className={`compare-pill${compare.includes(product.id)?" chosen":""}`} onClick={()=>toggleCompare(product)}>{compare.includes(product.id)?<Check size={13}/>:<Plus size={13}/>} Compare</button><button className="quick-add" aria-label={`Add ${product.name} to bag`} onClick={()=>addToCart(product)}><Plus size={18}/></button></div>
        <div className="product-info"><div className="product-overline"><span>{product.brand}</span><span className="rating">★ {product.rating} <i>({product.review_count})</i></span></div><div className="product-title-line"><button className="product-title-button" onClick={()=>setDetailProduct(product)}>{product.name}</button><span>{currency(product.price)}</span></div><p>{product.tagline}</p><button className="product-details" onClick={()=>setDetailProduct(product)}>Explore the details <ArrowUpRight size={13}/></button></div>
      </article>)}</div>
      {!loading&&products.length===0&&<div className="empty-results"><Search size={28}/><h3>Nothing in this corner just yet.</h3><p>Try a different search or browse all products.</p><button className="button button-outline" onClick={()=>{setQuery("");setCategory("All products")}}>See all products</button></div>}
      <div className="collection-note"><span className="note-dash"/>The good stuff, without the guesswork.<span className="note-dash"/></div>
    </section>

    <section className="feature-story" id="story"><div className="story-art"><div className="story-circle circle-a"/><div className="story-circle circle-b"/><div className="story-device"><div className="speaker"><i/><i/><i/><b/></div></div><div className="story-note note-top">MADE FOR THE MOMENTS<br/>IN BETWEEN.</div><div className="story-note note-bottom">LESS NOISE.<br/>MORE OF WHAT MATTERS.</div><span className="story-squiggle">✳</span></div><div className="story-copy"><div className="eyebrow"><span className="eyebrow-line"/>A DIFFERENT KIND OF TECH STORE</div><h2>More thought.<br/><em>Less scrolling.</em></h2><p>Finding the right thing shouldn’t feel like homework. We bring together useful, beautifully made tech—and the details that help you choose with confidence.</p><p>And if you’re still not sure? HarizonAI is here to talk it through. Ask a question, compare a couple of things, or just tell us what you need.</p><button className="button button-dark" onClick={()=>setAssistantOpen(true)}>Meet HarizonAI <MessageCircle size={16}/></button><div className="story-footnote"><span>01 — CURATED, NEVER CROWDED</span><span>02 — A PERSON, WHEN YOU NEED ONE</span></div></div></section>

    <section className="newsletter"><div className="newsletter-orbit orbit-one"/><div className="newsletter-orbit orbit-two"/><div className="eyebrow"><span className="eyebrow-line"/>A GOOD NOTE, NOW AND THEN</div><h2>Good things are<br/><em>worth a note.</em></h2><p>New finds, small rituals, and the occasional very good deal.<br/>No noise. Unsubscribe whenever.</p><form onSubmit={e=>{e.preventDefault();setToast("Thanks — you’re on the list.");(e.currentTarget as HTMLFormElement).reset();}}><input type="email" placeholder="Your email address" required aria-label="Email address"/><button aria-label="Subscribe"><ArrowRight size={18}/></button></form><small>BY SUBSCRIBING, YOU AGREE TO OUR PRIVACY POLICY.</small><span className="newsletter-stamp">A<br/>·</span></section>

    <footer className="footer"><div className="footer-top"><div><a className="wordmark footer-brand" href="#top"><span className="brand-mark">H<span>·</span></span><span>HARIZON</span></a><p>A little more thought<br/>in the everyday.</p></div><div className="footer-links"><div><b>EXPLORE</b><a href="#shop">Shop all</a><a href="#shop" onClick={()=>setCategory("Audio")}>Audio</a><a href="#shop" onClick={()=>setCategory("Wearables")}>Wearables</a></div><div><b>HERE TO HELP</b><a href="#" onClick={e=>{e.preventDefault();setAssistantOpen(true)}}>Ask HarizonAI</a><a href="#" onClick={e=>{e.preventDefault();setAssistantOpen(true);setMessages(rows=>[...rows,{role:"assistant",text:"Standard delivery usually takes 3–6 business days. Orders above ₹5,000 ship free."}])}}>Shipping & returns</a><a href="#" onClick={e=>{e.preventDefault();setProfileOpen(true)}}>My account</a></div><div><b>THE DETAILS</b><a href="#">Our point of view</a><a href="#">Privacy, please</a><a href="#">Terms of use</a></div></div></div><div className="footer-bottom"><span>© 2026 HARIZON STUDIO. GOOD TECH, THOUGHTFULLY FOUND.</span><span>MADE FOR EVERYDAY, EVERYWHERE.</span><button onClick={()=>window.scrollTo({top:0,behavior:"smooth"})}>BACK TO THE TOP <ArrowUp size={13}/></button></div></footer>

    <button className={`assistant-fab${assistantOpen?" fab-open":""}`} onClick={()=>setAssistantOpen(v=>!v)} aria-label={assistantOpen?"Close HarizonAI assistant":"Talk to HarizonAI, your shopping assistant"}>{assistantOpen?<X size={21}/>:<><span className="fab-spark"><Sparkles size={17}/></span><span>Ask HarizonAI</span><span className="fab-wave"><i/><i/><i/><i/></span></>}</button>
    {assistantOpen&&<aside className="assistant-panel" aria-label="HarizonAI shopping assistant"><div className="assistant-head"><span className="assistant-avatar"><Sparkles size={18}/></span><div><b>HarizonAI</b><small><i/> HERE TO HELP YOU FIND YOURS</small></div><button aria-label="Close assistant" onClick={()=>setAssistantOpen(false)}><X size={18}/></button></div><div className="assistant-intro"><span>YOUR THOUGHTFUL SHOPPING COMPANION</span><p>Ask about products, compare a couple, or get a straight answer on delivery and returns.</p></div>{process.env.NEXT_PUBLIC_LIVEKIT_MODE === "livekit" && <div className="live-voice-wrap"><LiveVoice onClose={()=>setAssistantOpen(false)}/></div>}<div className="assistant-messages">{messages.map((m,i)=><div key={`${i}-${m.role}`} className={`chat-message ${m.role}`}>{m.role==="assistant"&&<span className="chat-avatar"><Sparkles size={12}/></span>}<p>{m.text}</p></div>)}{chatBusy&&<div className="chat-message assistant"><span className="chat-avatar"><Sparkles size={12}/></span><p className="typing"><i/><i/><i/></p></div>}</div><div className="assistant-suggestions">{["What’s good for travel?","Tell me about returns"].map(t=><button key={t} onClick={()=>void sendMessage(t)}>{t}<ArrowUpRight size={12}/></button>)}</div><div className="chat-composer"><button className={`mic-button${listening?" listening":""}`} aria-label="Speak a question" onClick={startVoice}><Mic size={17}/></button><input value={chatText} onChange={e=>setChatText(e.target.value)} onKeyDown={e=>{if(e.key==="Enter")void sendMessage();}} placeholder="Ask me anything…" aria-label="Message HarizonAI"/><button className="send-button" onClick={()=>void sendMessage()} aria-label="Send message"><ArrowRight size={17}/></button></div><div className="assistant-foot">HARIZONAI CAN MAKE MISTAKES. ALWAYS CHECK PRODUCT DETAILS.</div><button className="ticket-link" onClick={()=>void createSupportTicket()}>Need a human? Request a support ticket <ArrowUpRight size={13}/></button></aside>}

    {compare.length>0&&<div className="compare-dock"><div><b>{compare.length} selected to compare</b><small>{compareProducts.map(p=>p.name).join(" · ")}</small></div><button className="compare-view" onClick={()=>setCompareOpen(true)}>Compare now <ArrowRight size={15}/></button><button className="dock-close" onClick={()=>setCompare([])} aria-label="Clear comparison"><X size={16}/></button></div>}
    {compareOpen&&<div className="modal-backdrop" onClick={()=>setCompareOpen(false)}><section className="compare-modal" onClick={e=>e.stopPropagation()}><div className="modal-top"><div><div className="eyebrow"><span className="eyebrow-line"/>SIDE BY SIDE</div><h2>A closer <em>look.</em></h2></div><button className="icon-button" onClick={()=>setCompareOpen(false)} aria-label="Close"><X size={20}/></button></div><div className="compare-table"><div className="compare-labels"><b>THE DETAILS</b>{["Price","Rating","Category",...Array.from(new Set(compareProducts.flatMap(p=>Object.keys(p.specs))))].map(name=><span key={name}>{name}</span>)}</div>{compareProducts.map(p=><div className="compare-column" key={p.id}><div className="compare-art" style={{background:p.color}}><ProductArt product={p}/></div><b>{p.name}</b><strong>{currency(p.price)}</strong><span>{p.rating} / 5</span><span>{p.category}</span>{Array.from(new Set(compareProducts.flatMap(x=>Object.keys(x.specs)))).map(key=><span key={key}>{p.specs[key]||"—"}</span>)}</div>)}</div></section></div>}
    {detailProduct&&<div className="modal-backdrop" onClick={()=>setDetailProduct(null)}><section className="detail-modal" onClick={e=>e.stopPropagation()}><button className="detail-close icon-button" onClick={()=>setDetailProduct(null)} aria-label="Close product details"><X size={19}/></button><div className="detail-visual" style={{background:detailProduct.color}}><ProductArt product={detailProduct} large/><span>{detailProduct.brand} · {detailProduct.category}</span></div><div className="detail-copy"><div className="eyebrow"><span className="eyebrow-line"/>A CLOSER LOOK</div><h2>{detailProduct.name}</h2><p className="detail-tagline">{detailProduct.tagline}</p><p className="detail-description">{detailProduct.description}</p><div className="detail-price"><b>{currency(detailProduct.price)}</b>{detailProduct.compare_at&&<del>{currency(detailProduct.compare_at)}</del>}<span>★ {detailProduct.rating} · {detailProduct.review_count} considered reviews</span></div><div className="detail-specs">{Object.entries(detailProduct.specs).map(([key,value])=><div key={key}><span>{key}</span><b>{value}</b></div>)}</div><button className="button button-dark detail-add" onClick={()=>{addToCart(detailProduct);setDetailProduct(null);}}>Add to your bag <span>{currency(detailProduct.price)}</span><ShoppingBag size={15}/></button><button className="detail-ask" onClick={()=>{const prompt=`Tell me about ${detailProduct.name}`;setAssistantOpen(true);setDetailProduct(null);void sendMessage(prompt);}}>Ask HarizonAI about this one <ArrowRight size={14}/></button></div></section></div>}
    {cartOpen&&<div className="drawer-backdrop" onClick={()=>setCartOpen(false)}><aside className="cart-drawer" onClick={e=>e.stopPropagation()}><div className="drawer-head"><div><span>YOUR BAG</span><h2>Good choices.</h2></div><button className="icon-button" onClick={()=>setCartOpen(false)} aria-label="Close bag"><X size={20}/></button></div>{cart.length===0?<div className="empty-cart"><ShoppingBag size={34}/><h3>Your bag has room.</h3><p>Find a few things that feel like you.</p><button className="button button-dark" onClick={()=>setCartOpen(false)}>Explore the collection <ArrowRight size={15}/></button></div>:<><div className="shipping-progress"><div><Truck size={16}/><span>{subtotal>=5000?"You’ve unlocked complimentary delivery.":`You’re ${currency(5000-subtotal)} away from complimentary delivery.`}</span></div><i><b style={{width:`${Math.min(100,subtotal/50)}%`}}/></i></div><div className="cart-lines">{cart.map(row=><article className="cart-line" key={row.product.id}><div style={{background:row.product.color}}><ProductArt product={row.product}/></div><section><small>{row.product.brand}</small><b>{row.product.name}</b><span>{currency(row.product.price)}</span><div className="quantity-control"><button onClick={()=>changeQuantity(row.product.id,-1)} aria-label="Decrease quantity"><Minus size={13}/></button><span>{row.quantity}</span><button onClick={()=>changeQuantity(row.product.id,1)} aria-label="Increase quantity"><Plus size={13}/></button></div></section><button className="remove-line" onClick={()=>changeQuantity(row.product.id,-row.quantity)} aria-label={`Remove ${row.product.name}`}><X size={15}/></button></article>)}</div><div className="cart-summary"><div><span>Subtotal</span><b>{currency(subtotal)}</b></div><p>Shipping calculated at checkout.</p><button className="button button-dark checkout-cta" onClick={()=>{setCartOpen(false);setCheckoutOpen(true)}}>Continue to checkout <ArrowRight size={16}/></button><small><ShieldCheck size={13}/> A secure, easy checkout.</small></div></>}</aside></div>}
    {checkoutOpen&&<div className="modal-backdrop" onClick={()=>setCheckoutOpen(false)}><section className="checkout-modal" onClick={e=>e.stopPropagation()}><div className="modal-top"><div><div className="eyebrow"><span className="eyebrow-line"/>A FEW DETAILS</div><h2>Let’s get it <em>to you.</em></h2></div><button className="icon-button" onClick={()=>setCheckoutOpen(false)} aria-label="Close checkout"><X size={20}/></button></div><div className="checkout-total"><span>{totalCount} item{totalCount===1?"":"s"} · Pay securely in INR</span><b>{currency(subtotal+(subtotal>=5000?0:99))}</b></div><form className="checkout-form" onSubmit={submitCheckout}><label>Full name<input name="full_name" required minLength={2} autoComplete="name" placeholder="Your name"/></label><label>Address line 1<input name="line1" required minLength={4} autoComplete="address-line1" placeholder="House / flat, street"/></label><label>Address line 2 <small>OPTIONAL</small><input name="line2" autoComplete="address-line2" placeholder="Apartment, landmark"/></label><div className="address-row"><label>City<input name="city" required autoComplete="address-level2" placeholder="City"/></label><label>State<input name="state" required autoComplete="address-level1" placeholder="State"/></label></div><label>PIN code<input name="postal_code" required pattern="[0-9]{6}" inputMode="numeric" autoComplete="postal-code" placeholder="6-digit PIN"/></label><button className="button button-dark checkout-cta" type="submit">Place order <ArrowRight size={16}/></button><p className="payment-note"><ShieldCheck size={14}/> {customer?.authenticated?`Signed in as ${customer.email}`:"You’ll need to sign in before placing your order."} In local mode, checkout uses a test payment.</p></form></section></div>}
    {profileOpen&&<div className="modal-backdrop" onClick={()=>setProfileOpen(false)}><section className="profile-modal" onClick={e=>e.stopPropagation()}><div className="modal-top"><div><div className="eyebrow"><span className="eyebrow-line"/>YOUR HARIZON ACCOUNT</div><h2>{customer?.authenticated?`Hello, ${(customerName || customer.email.split("@")[0]).split(" ")[0]}.`:"Come on in."}</h2></div><button className="icon-button" onClick={()=>setProfileOpen(false)} aria-label="Close account"><X size={20}/></button></div>{customer?.authenticated?<><p className="account-email">Signed in as <b>{customer.email}</b></p><button className="button button-dark checkout-cta" onClick={()=>void loadCustomerOrders()} disabled={ordersLoading}>{ordersLoading?"Loading your orders…":"View my orders"} <ArrowRight size={15}/></button>{ordersError&&<p className="orders-error" role="alert">{ordersError}</p>}{ordersLoaded&&customerOrders.length===0&&<div className="orders-empty"><b>No orders for this account yet.</b><span>If you checked out using another sign-in option, try signing in with that same option.</span></div>}{customerOrders.length>0&&<div className="account-orders" aria-live="polite"><h3>Your orders <span>{customerOrders.length}</span></h3>{customerOrders.map(order=><article className="account-order" key={order.id}><div className="account-order-head"><div><b>Order {order.order_reference}</b><time dateTime={order.created_at}>{new Intl.DateTimeFormat("en-IN",{dateStyle:"medium",timeStyle:"short"}).format(new Date(order.created_at))}</time></div><div><strong>{currency(order.total)}</strong><span>{order.status.replaceAll("_"," ")} · {order.payment_status.replaceAll("_"," ")}</span></div></div><ul>{order.items.map((item,index)=><li key={`${item.product_id}-${index}`}><span>{item.product_name} <small>× {item.quantity}</small></span><span>{currency(item.unit_price * item.quantity)}</span></li>)}</ul><div className="account-order-total"><span>Subtotal {currency(order.subtotal)} · Shipping {currency(order.shipping)}</span><b>Total {currency(order.total)}</b></div></article>)}</div>}<button className="text-action" onClick={()=>void signOut()}>Sign out</button></>:<><p>Sign in to keep your orders, addresses and good finds all in one place.</p><button className="button button-dark checkout-cta" onClick={()=>void signIn()}>{authMode === "auth0" ? "Continue with email or SSO" : "Continue with local test account"} <ArrowRight size={15}/></button>{authMode !== "auth0" && <small className="dev-note">LOCAL DEVELOPMENT SIGN-IN · SYNTHETIC ACCOUNT</small>}</>}</section></div>}
    {toast&&<div className="toast"><Check size={16}/>{toast}</div>}
  </main>;
}

