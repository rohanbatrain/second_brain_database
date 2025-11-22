"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

interface HeaderProps {
    appName: string;
    appIcon: React.ReactNode;
    primaryColor?: string;
}

export default function Header({ appName, appIcon, primaryColor = "indigo" }: HeaderProps) {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    const colorClasses = {
        indigo: "from-indigo-600 to-indigo-800 border-indigo-500/50",
        emerald: "from-emerald-600 to-emerald-800 border-emerald-500/50",
        pink: "from-pink-600 to-pink-800 border-pink-500/50",
        cyan: "from-cyan-600 to-cyan-800 border-cyan-500/50",
        amber: "from-amber-600 to-amber-800 border-amber-500/50",
        violet: "from-violet-600 to-violet-800 border-violet-500/50",
    };

    const buttonClass = colorClasses[primaryColor as keyof typeof colorClasses] || colorClasses.indigo;

    return (
        <motion.header
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            className="fixed top-0 left-0 right-0 z-50 bg-[#0D0E0F]/80 backdrop-blur-md border-b border-white/10"
        >
            <div className="container mx-auto px-4 h-16 flex items-center justify-between">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-2">
                    <div className="w-8 h-8 flex items-center justify-center">
                        {appIcon}
                    </div>
                    <span className="text-xl font-bold text-white">{appName}</span>
                </Link>

                {/* Desktop Navigation */}
                <nav className="hidden md:flex items-center gap-6">
                    <Link href="/" className="text-white/80 hover:text-white transition-colors">
                        Home
                    </Link>
                    <Link href="/dashboard" className="text-white/80 hover:text-white transition-colors">
                        Dashboard
                    </Link>
                    <Link href="https://github.com/rohanbatrain/second_brain_database" target="_blank" rel="noopener noreferrer" className="text-white/80 hover:text-white transition-colors">
                        GitHub
                    </Link>
                </nav>

                {/* CTA Buttons */}
                <div className="hidden md:flex items-center gap-4">
                    <Link href="/auth/login">
                        <button className="px-6 py-2 text-white hover:bg-white/10 rounded-lg transition-colors border border-white/20">
                            Sign In
                        </button>
                    </Link>
                    <Link href="/auth/signup">
                        <button className={`px-6 py-2 bg-gradient-to-b ${buttonClass} text-white rounded-lg transition-all duration-300 border`}>
                            Get Started
                        </button>
                    </Link>
                </div>

                {/* Mobile Menu Button */}
                <button
                    onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    className="md:hidden text-white p-2"
                >
                    {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                </button>
            </div>

            {/* Mobile Menu */}
            {mobileMenuOpen && (
                <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="md:hidden bg-[#0D0E0F] border-t border-white/10"
                >
                    <div className="container mx-auto px-4 py-4 space-y-4">
                        <Link href="/" className="block text-white/80 hover:text-white py-2">
                            Home
                        </Link>
                        <Link href="/dashboard" className="block text-white/80 hover:text-white py-2">
                            Dashboard
                        </Link>
                        <Link href="https://github.com/rohanbatrain/second_brain_database" target="_blank" rel="noopener noreferrer" className="block text-white/80 hover:text-white py-2">
                            GitHub
                        </Link>
                        <div className="pt-4 space-y-2">
                            <Link href="/auth/login" className="block">
                                <button className="w-full px-6 py-2 text-white hover:bg-white/10 rounded-lg transition-colors border border-white/20">
                                    Sign In
                                </button>
                            </Link>
                            <Link href="/auth/signup" className="block">
                                <button className={`w-full px-6 py-2 bg-gradient-to-b ${buttonClass} text-white rounded-lg transition-all duration-300 border`}>
                                    Get Started
                                </button>
                            </Link>
                        </div>
                    </div>
                </motion.div>
            )}
        </motion.header>
    );
}
