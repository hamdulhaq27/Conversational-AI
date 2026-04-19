import { Link } from "react-router-dom";
import { ArrowLeft, Utensils } from "lucide-react";

const images = [
  { src: "/restaurant/1.jpg", label: "The Grand Dining Room" },
  { src: "/restaurant/2.jpg", label: "Intimate Candlelit Ambiance" },
  { src: "/restaurant/3.jpg", label: "The Bar Lounge" },
  { src: "/restaurant/4.jpg", label: "Evening Service" },
  { src: "/restaurant/5.jpg", label: "Chef's Table Experience" },
  { src: "/restaurant/6.jpg", label: "Private Dining Room" },
  { src: "/restaurant/7.jpg", label: "The Wine Cellar" },
  { src: "/restaurant/8.jpg", label: "Terrace & Garden" },
];

export default function GalleryPage() {
  return (
    <div className="min-h-screen bg-stone-950">
      {/* Navbar */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-stone-950/95 backdrop-blur-md border-b border-stone-800 py-4">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <ArrowLeft className="w-4 h-4 text-stone-400 group-hover:text-amber-500 transition-colors" />
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 bg-gradient-to-br from-amber-600 to-red-700 rounded-full flex items-center justify-center">
                <Utensils className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="font-serif text-white font-bold">La Bella Tavola</span>
            </div>
          </Link>
          <p className="text-amber-500 text-xs tracking-[0.3em] uppercase font-semibold">Gallery</p>
        </div>
      </nav>

      {/* Hero */}
      <div className="relative pt-20 pb-16 text-center px-6">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(180,83,9,0.15),_transparent_60%)]" />
        <div className="relative z-10 max-w-3xl mx-auto pt-12">
          <p className="text-amber-500 text-xs tracking-[0.35em] uppercase font-semibold mb-4">Our World</p>
          <h1 className="font-serif text-5xl md:text-6xl font-bold text-white mb-5 leading-tight">
            A Gallery of<br /><span className="text-amber-400">Excellence</span>
          </h1>
          <p className="text-stone-400 text-lg leading-relaxed">
            Step inside La Bella Tavola — where three decades of artistry, warmth, and culinary mastery converge in every corner of our Mayfair home.
          </p>
        </div>
      </div>

      {/* Masonry-style gallery */}
      <div className="max-w-7xl mx-auto px-6 pb-24">
        <div className="columns-2 md:columns-3 lg:columns-4 gap-4 space-y-4">
          {images.map((img, i) => (
            <div
              key={i}
              className={`break-inside-avoid group relative overflow-hidden rounded-2xl cursor-pointer ${i % 3 === 0 ? "row-span-2" : ""}`}
            >
              <img
                src={img.src}
                alt={img.label}
                className="w-full object-cover transition-transform duration-700 group-hover:scale-110"
                style={{ height: i % 3 === 0 ? "380px" : i % 5 === 0 ? "280px" : "220px" }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end p-5">
                <div>
                  <p className="text-amber-400 text-xs tracking-widest uppercase font-semibold mb-1">La Bella Tavola</p>
                  <p className="text-white font-serif text-lg font-bold">{img.label}</p>
                </div>
              </div>
              <div className="absolute top-3 right-3 bg-black/40 backdrop-blur-sm text-white text-xs px-2 py-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                {String(i + 1).padStart(2, "0")} / {String(images.length).padStart(2, "0")}
              </div>
            </div>
          ))}
        </div>

        {/* Divider / Call to action */}
        <div className="mt-20 text-center">
          <div className="w-16 h-px bg-amber-600 mx-auto mb-8" />
          <h2 className="font-serif text-3xl font-bold text-white mb-4">Experience It In Person</h2>
          <p className="text-stone-400 mb-8 max-w-md mx-auto">Every photograph captures a moment — but nothing compares to the real thing. Reserve your table and become part of our story.</p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 bg-gradient-to-r from-amber-600 to-red-700 text-white px-8 py-4 rounded-full font-semibold tracking-wide hover:shadow-2xl hover:shadow-amber-500/30 transition-all duration-300 hover:scale-105"
          >
            Reserve a Table
          </Link>
        </div>
      </div>

      {/* Footer bar */}
      <div className="border-t border-stone-800 py-6 text-center">
        <p className="text-stone-600 text-xs">© 2024 La Bella Tavola · 24 Berkeley Square, Mayfair, London · 2 Michelin Stars</p>
      </div>
    </div>
  );
}
