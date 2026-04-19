import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { MessageCircle, Star, MapPin, Phone, Mail, Clock, ChevronDown, Award, Utensils, Wine, X } from "lucide-react";
import { ChatWindow } from "@/components/ChatWindow";

const Navbar = ({ onChatOpen }: { onChatOpen: () => void }) => {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${scrolled ? "bg-white/95 backdrop-blur-md shadow-md py-3" : "bg-transparent py-6"}`}>
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-amber-600 to-red-700 rounded-full flex items-center justify-center">
            <Utensils className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className={`font-serif text-xl font-bold tracking-wide transition-colors ${scrolled ? "text-stone-900" : "text-white"}`}>La Bella Tavola</span>
            <p className={`text-xs tracking-[0.2em] uppercase transition-colors ${scrolled ? "text-amber-700" : "text-amber-300"}`}>Michelin Star · Est. 1987</p>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-8">
          {["About", "Menu", "Gallery", "Reservations"].map((item) => (
            item === "Gallery" ? (
              <Link key={item} to="/gallery" className={`text-sm font-medium tracking-wide transition-colors hover:text-amber-500 ${scrolled ? "text-stone-700" : "text-white/90"}`}>
                {item}
              </Link>
            ) : (
              <a key={item} href={`#${item.toLowerCase()}`} className={`text-sm font-medium tracking-wide transition-colors hover:text-amber-500 ${scrolled ? "text-stone-700" : "text-white/90"}`}>
                {item}
              </a>
            )
          ))}
        </div>

        <button
          onClick={onChatOpen}
          className="flex items-center gap-2 bg-gradient-to-r from-amber-600 to-red-700 text-white px-5 py-2.5 rounded-full text-sm font-semibold hover:shadow-lg hover:shadow-amber-500/30 transition-all duration-300 hover:scale-105"
        >
          <MessageCircle className="w-4 h-4" />
          Reserve a Table
        </button>
      </div>
    </nav>
  );
};

const Hero = ({ onChatOpen }: { onChatOpen: () => void }) => (
  <section className="relative h-screen flex items-center justify-center overflow-hidden">
    <div className="absolute inset-0">
      <img src="/restaurant/4.jpg" alt="La Bella Tavola interior" className="w-full h-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/40 to-black/70" />
    </div>
    <div className="relative z-10 text-center text-white max-w-4xl px-6">
      <p className="text-amber-400 text-sm tracking-[0.35em] uppercase mb-4 font-light">Welcome to</p>
      <h1 className="font-serif text-6xl md:text-8xl font-bold mb-6 leading-tight" style={{ textShadow: "0 4px 20px rgba(0,0,0,0.5)" }}>
        La Bella<br /><span className="text-amber-400">Tavola</span>
      </h1>
      <p className="text-white/80 text-lg md:text-xl font-light mb-2 tracking-wide">An Unparalleled Italian·Mediterranean Fine Dining Experience</p>
      <p className="text-amber-300/80 text-sm tracking-[0.25em] uppercase mb-10">2 Michelin Stars · London, Mayfair</p>
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <button
          onClick={onChatOpen}
          className="bg-gradient-to-r from-amber-600 to-red-700 text-white px-8 py-4 rounded-full font-semibold text-base tracking-wide hover:shadow-2xl hover:shadow-amber-500/40 transition-all duration-300 hover:scale-105"
        >
          Reserve Your Table
        </button>
        <a href="#about" className="border border-white/40 text-white px-8 py-4 rounded-full font-medium text-base tracking-wide hover:bg-white/10 transition-all duration-300">
          Discover More
        </a>
      </div>
    </div>
    <a href="#about" className="absolute bottom-8 left-1/2 -translate-x-1/2 text-white/60 animate-bounce">
      <ChevronDown className="w-8 h-8" />
    </a>
  </section>
);

const Awards = () => (
  <section className="bg-stone-900 py-6">
    <div className="max-w-7xl mx-auto px-6 flex flex-wrap items-center justify-center gap-10 md:gap-20">
      {[
        { label: "Michelin Stars", value: "2 ★★", sub: "Awarded 2019 & 2022" },
        { label: "Wine Spectator", value: "Best of", sub: "Award of Excellence" },
        { label: "Forbes Travel", value: "5 Star", sub: "Rated Restaurant" },
        { label: "Zagat Rated", value: "28/30", sub: "Exceptional Experience" },
      ].map((a) => (
        <div key={a.label} className="text-center">
          <p className="text-amber-400 text-xl font-bold font-serif">{a.value}</p>
          <p className="text-white text-sm font-medium">{a.label}</p>
          <p className="text-stone-400 text-xs">{a.sub}</p>
        </div>
      ))}
    </div>
  </section>
);

const About = () => (
  <section id="about" className="py-28 bg-white">
    <div className="max-w-7xl mx-auto px-6 grid md:grid-cols-2 gap-16 items-center">
      <div>
        <p className="text-amber-600 text-xs tracking-[0.3em] uppercase font-semibold mb-4">Our Heritage</p>
        <h2 className="font-serif text-5xl font-bold text-stone-900 leading-tight mb-6">
          An Upscale<br />Italian Experience
        </h2>
        <p className="text-stone-600 text-base leading-relaxed mb-6">
          Nestled in the heart of London's Mayfair, La Bella Tavola has redefined fine dining since 1987. Founded by Master Chef Marco Conti, our philosophy is simple: only the finest seasonal ingredients, prepared with classical technique and modern artistry.
        </p>
        <p className="text-stone-600 text-base leading-relaxed mb-8">
          Our cellar houses over 3,000 labels across 14 regions of Italy and France. Every dish tells a story — from the handmade tagliatelle sourced from an 18th-century recipe to our legendary osso buco, slow-braised for 8 hours.
        </p>
        <div className="flex gap-8">
          {[{ n: "35+", l: "Years of Excellence" }, { n: "120", l: "Seats, All Private" }, { n: "3,200+", l: "Labels in Cellar" }].map((s) => (
            <div key={s.l}>
              <p className="font-serif text-3xl font-bold text-amber-700">{s.n}</p>
              <p className="text-xs text-stone-500 uppercase tracking-wide mt-1">{s.l}</p>
            </div>
          ))}
        </div>
      </div>
      <div className="relative">
        <img src="/restaurant/1.jpg" alt="Restaurant interior" className="w-full h-[520px] object-cover rounded-2xl shadow-2xl" />
        <div className="absolute -bottom-6 -left-6 w-40 h-40 rounded-xl overflow-hidden border-4 border-white shadow-xl">
          <img src="/chef.jpg" alt="Head Chef" className="w-full h-full object-cover" />
        </div>
        <div className="absolute -top-4 -right-4 bg-amber-600 text-white p-4 rounded-xl shadow-lg text-center">
          <Award className="w-6 h-6 mx-auto mb-1" />
          <p className="text-xs font-bold uppercase tracking-wide">Michelin</p>
          <p className="text-lg font-serif font-bold">★★</p>
        </div>
      </div>
    </div>
  </section>
);

const SignatureDishes = () => (
  <section id="menu" className="py-28 bg-stone-50">
    <div className="max-w-7xl mx-auto px-6">
      <div className="text-center mb-16">
        <p className="text-amber-600 text-xs tracking-[0.3em] uppercase font-semibold mb-3">Signature Creations</p>
        <h2 className="font-serif text-5xl font-bold text-stone-900">Our Celebrated Menu</h2>
        <p className="text-stone-500 mt-4 max-w-xl mx-auto">Crafted daily from the finest seasonal produce, each dish a masterclass in Italian culinary tradition.</p>
      </div>
      <div className="grid md:grid-cols-3 gap-8">
        {[
          { img: "/pizza.jpg", name: "Truffle Margherita", cat: "Wood-Fired Classics", desc: "San Marzano tomatoes, buffalo mozzarella di bufala, 24-month Parmigiano, black Périgord truffle shavings", price: "£42" },
          { img: "/pasta.jpg", name: "Tagliatelle al Ragù", cat: "Handmade Pasta", desc: "48-hour slow-braised Wagyu beef ragù, hand-rolled egg tagliatelle, aged Parmigiano Reggiano", price: "£54" },
          { img: "/steak.png", name: "Bistecca Fiorentina", cat: "Griglia Principali", desc: "28-day dry-aged Hereford T-bone, rosemary & garlic, hazelnut butter, truffle roasted potatoes", price: "£98" },
        ].map((dish) => (
          <div key={dish.name} className="group bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-500 hover:-translate-y-2">
            <div className="relative h-56 overflow-hidden">
              <img src={dish.img} alt={dish.name} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
              <div className="absolute top-4 left-4 bg-amber-600 text-white text-xs font-semibold px-3 py-1 rounded-full uppercase tracking-wide">
                {dish.cat}
              </div>
            </div>
            <div className="p-6">
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-serif text-xl font-bold text-stone-900">{dish.name}</h3>
                <span className="text-amber-700 font-bold text-lg font-serif">{dish.price}</span>
              </div>
              <p className="text-stone-500 text-sm leading-relaxed">{dish.desc}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="text-center mt-12">
        <a href="#reservations" className="inline-flex items-center gap-2 border-2 border-amber-600 text-amber-700 px-8 py-3 rounded-full font-semibold hover:bg-amber-600 hover:text-white transition-all duration-300">
          <Utensils className="w-4 h-4" />
          View Full Tasting Menu
        </a>
      </div>
    </div>
  </section>
);

const Experience = () => (
  <section className="py-0 bg-white">
    <div className="grid md:grid-cols-2 min-h-[600px]">
      <div className="relative overflow-hidden">
        <img src="/restaurant/3.jpg" alt="Dining room" className="w-full h-full object-cover min-h-[500px]" />
        <div className="absolute inset-0 bg-black/20" />
      </div>
      <div className="flex items-center bg-stone-900 p-14 md:p-20">
        <div>
          <p className="text-amber-500 text-xs tracking-[0.3em] uppercase font-semibold mb-4">The Experience</p>
          <h2 className="font-serif text-4xl font-bold text-white leading-tight mb-6">
            Where Every Meal<br />Becomes a Memory
          </h2>
          <p className="text-stone-400 leading-relaxed mb-6">
            From the moment you arrive, every detail has been considered. Our sommelier team curates a personalised wine journey, while our service is as warm as the Tuscan sun.
          </p>
          <p className="text-stone-400 leading-relaxed mb-8">
            Private dining rooms accommodate intimate gatherings of up to 24 guests. Bespoke menus, floral arrangements, and a dedicated butler are all standard inclusions.
          </p>
          <div className="space-y-3">
            {["Private Dining Rooms Available", "Award-Winning Wine Programme", "Tasting Menus from £145/Person", "Vegetarian & Vegan Menus On Request"].map((f) => (
              <div key={f} className="flex items-center gap-3">
                <div className="w-1.5 h-1.5 bg-amber-500 rounded-full" />
                <p className="text-stone-300 text-sm">{f}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  </section>
);

const GalleryPreview = () => (
  <section className="py-20 bg-stone-50">
    <div className="max-w-7xl mx-auto px-6">
      <div className="text-center mb-12">
        <p className="text-amber-600 text-xs tracking-[0.3em] uppercase font-semibold mb-3">Inside La Bella Tavola</p>
        <h2 className="font-serif text-4xl font-bold text-stone-900">A Glimpse of Excellence</h2>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {["/restaurant/2.jpg", "/restaurant/5.jpg", "/restaurant/6.jpg", "/restaurant/7.jpg"].map((src, i) => (
          <div key={i} className={`relative overflow-hidden rounded-xl ${i === 0 ? "row-span-2" : ""} group`}>
            <img src={src} alt={`Gallery ${i + 1}`} className={`w-full object-cover group-hover:scale-110 transition-transform duration-700 ${i === 0 ? "h-full min-h-[320px]" : "h-40 md:h-48"}`} />
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-300" />
          </div>
        ))}
      </div>
      <div className="text-center mt-8">
        <Link to="/gallery" className="inline-flex items-center gap-2 bg-stone-900 text-white px-8 py-3 rounded-full font-semibold text-sm tracking-wide hover:bg-stone-700 transition-colors">
          View Full Gallery
        </Link>
      </div>
    </div>
  </section>
);

const Reviews = () => {
  const reviews = [
    { name: "Sir James Hartwell", role: "Food Critic, The Times", rating: 5, text: "La Bella Tavola is the pinnacle of Italian fine dining in London. The truffle tagliatelle was transcendent — a dish I will dream about until I return. The wine programme is unrivalled in the capital." },
    { name: "Elena Rosenberg", role: "Forbes Travel Contributor", rating: 5, text: "An immaculate experience from start to finish. Chef Conti's Fiorentina Bistecca was the finest steak I've consumed in a decade of reviewing. The service is discreet, warm, and utterly professional." },
    { name: "Dr. Priya Mehta", role: "Luxury Lifestyle Magazine", rating: 5, text: "We celebrated our anniversary here and were treated like royalty. The private dining room was breathtaking. Every element — lighting, music, plating — was curated with exceptional artistry." },
  ];

  return (
    <section className="py-28 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-16">
          <p className="text-amber-600 text-xs tracking-[0.3em] uppercase font-semibold mb-3">Testimonials</p>
          <h2 className="font-serif text-5xl font-bold text-stone-900">What Our Guests Say</h2>
        </div>
        <div className="grid md:grid-cols-3 gap-8">
          {reviews.map((r) => (
            <div key={r.name} className="bg-stone-50 rounded-2xl p-8 border border-stone-100 hover:shadow-xl transition-shadow duration-300">
              <div className="flex mb-4">
                {Array.from({ length: r.rating }).map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-amber-500 text-amber-500" />
                ))}
              </div>
              <p className="text-stone-700 leading-relaxed text-sm italic mb-6">"{r.text}"</p>
              <div className="flex items-center gap-3 pt-4 border-t border-stone-200">
                <div className="w-10 h-10 bg-gradient-to-br from-amber-500 to-red-600 rounded-full flex items-center justify-center text-white font-bold text-sm font-serif">
                  {r.name[0]}
                </div>
                <div>
                  <p className="font-semibold text-stone-900 text-sm">{r.name}</p>
                  <p className="text-xs text-stone-500">{r.role}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

const Reservations = ({ onChatOpen }: { onChatOpen: () => void }) => (
  <section id="reservations" className="relative py-28 overflow-hidden">
    <div className="absolute inset-0">
      <img src="/restaurant/8.jpg" alt="Restaurant atmosphere" className="w-full h-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-r from-stone-900/95 via-stone-900/80 to-transparent" />
    </div>
    <div className="relative z-10 max-w-7xl mx-auto px-6">
      <div className="max-w-xl">
        <p className="text-amber-400 text-xs tracking-[0.3em] uppercase font-semibold mb-4">Reservations</p>
        <h2 className="font-serif text-5xl font-bold text-white leading-tight mb-6">
          Reserve Your<br />Table Tonight
        </h2>
        <p className="text-stone-400 leading-relaxed mb-8">
          We recommend booking at least 2 weeks in advance for weekend evenings. Our reservation concierge is available 7 days a week to accommodate special requests.
        </p>
        <div className="space-y-4 mb-10">
          {[
            { icon: Clock, text: "Lunch: 12:00 PM — 3:00 PM | Dinner: 6:30 PM — 11:00 PM" },
            { icon: Phone, text: "+44 20 7946 0958  ·  Available 10am–10pm daily" },
            { icon: MapPin, text: "24 Berkeley Square, Mayfair, London W1J 6HB" },
          ].map(({ icon: Icon, text }) => (
            <div key={text} className="flex items-start gap-3">
              <Icon className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
              <p className="text-stone-300 text-sm">{text}</p>
            </div>
          ))}
        </div>
        <button
          onClick={onChatOpen}
          className="flex items-center gap-2 bg-gradient-to-r from-amber-600 to-red-700 text-white px-8 py-4 rounded-full font-semibold text-base tracking-wide hover:shadow-2xl hover:shadow-amber-500/40 transition-all duration-300 hover:scale-105"
        >
          <MessageCircle className="w-5 h-5" />
          Open Reservation Chat
        </button>
      </div>
    </div>
  </section>
);

const Footer = () => (
  <footer className="bg-stone-950 text-stone-400 py-16">
    <div className="max-w-7xl mx-auto px-6">
      <div className="grid md:grid-cols-4 gap-10 mb-12">
        <div className="md:col-span-2">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 bg-gradient-to-br from-amber-600 to-red-700 rounded-full flex items-center justify-center">
              <Utensils className="w-4 h-4 text-white" />
            </div>
            <span className="font-serif text-xl font-bold text-white">La Bella Tavola</span>
          </div>
          <p className="text-stone-500 text-sm leading-relaxed max-w-xs">
            London's most celebrated Italian fine dining destination, committed to an uncompromising standard of culinary excellence since 1987.
          </p>
          <div className="flex gap-3 mt-5">
            {["IG", "FB", "TW", "YT"].map((s) => (
              <div key={s} className="w-8 h-8 border border-stone-700 rounded-full flex items-center justify-center text-stone-500 hover:border-amber-600 hover:text-amber-500 cursor-pointer transition-colors text-xs font-bold">
                {s}
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 className="text-white font-semibold text-sm tracking-wide uppercase mb-4">Navigate</h4>
          <ul className="space-y-2.5">
            {["About Us", "The Menu", "Gallery", "Private Dining", "Our Team", "Press"].map((item) => (
              <li key={item}><a href="#" className="text-stone-500 text-sm hover:text-amber-500 transition-colors">{item}</a></li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-white font-semibold text-sm tracking-wide uppercase mb-4">Contact</h4>
          <ul className="space-y-3">
            {[
              { icon: MapPin, text: "24 Berkeley Square, Mayfair, London W1J 6HB" },
              { icon: Phone, text: "+44 20 7946 0958" },
              { icon: Mail, text: "reservations@lbt.co.uk" },
              { icon: Clock, text: "Open daily 12PM – 11PM" },
            ].map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-2.5">
                <Icon className="w-3.5 h-3.5 text-amber-600 mt-0.5 flex-shrink-0" />
                <span className="text-stone-500 text-sm">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-stone-800 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-stone-600 text-xs">© 2024 La Bella Tavola. All rights reserved.</p>
        <p className="text-stone-600 text-xs flex items-center gap-1.5">
          <Wine className="w-3 h-3 text-amber-700" />
          Awarded 2 Michelin Stars · Forbes 5-Star · Wine Spectator Excellence
        </p>
      </div>
    </div>
  </footer>
);

const ChatModal = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl h-[85vh] sm:h-[80vh] rounded-t-3xl sm:rounded-3xl overflow-hidden shadow-2xl flex flex-col">
        <button onClick={onClose} className="absolute top-4 right-4 z-10 bg-white/10 backdrop-blur-sm rounded-full p-2 hover:bg-white/20 transition-colors">
          <X className="w-5 h-5 text-white" />
        </button>
        <ChatWindow />
      </div>
    </div>
  );
};

export default function HomePage() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white">
      <Navbar onChatOpen={() => setChatOpen(true)} />
      <Hero onChatOpen={() => setChatOpen(true)} />
      <Awards />
      <About />
      <SignatureDishes />
      <Experience />
      <GalleryPreview />
      <Reviews />
      <Reservations onChatOpen={() => setChatOpen(true)} />
      <Footer />
      <ChatModal open={chatOpen} onClose={() => setChatOpen(false)} />

      {/* Floating chat button */}
      <button
        onClick={() => setChatOpen(true)}
        className="fixed bottom-8 right-8 z-40 bg-gradient-to-r from-amber-600 to-red-700 text-white rounded-full p-4 shadow-2xl shadow-amber-500/40 hover:scale-110 transition-transform duration-300"
        title="Open Reservation Chat"
      >
        <MessageCircle className="w-6 h-6" />
      </button>
    </div>
  );
}
