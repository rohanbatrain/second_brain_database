"use client";

import { Github, BookOpen, Brain, Sparkles, Zap, Database } from "lucide-react";
import Link from "next/link";

export default function Footer() {
    const currentYear = new Date().getFullYear();

    return (
        <footer className="w-full bg-gradient-to-b from-[#0C0F15] to-black border-t border-white/10 py-16">
            <div className="container mx-auto px-4">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 max-w-7xl mx-auto">
                    {/* Brand Section */}
                    <div className="lg:col-span-1">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                                <Brain className="w-6 h-6 text-white" />
                            </div>
                            <h3 className="text-2xl font-bold text-white">MemEx</h3>
                        </div>
                        <p className="text-white/70 mb-6 text-sm leading-relaxed">
                            Your personal memory extension system. Capture, organize, and discover knowledge with intelligent connections.
                        </p>
                        <div className="flex gap-4">
                            <a
                                href="https://github.com/rohanbatrain/second_brain_database"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-10 h-10 bg-white/5 hover:bg-white/10 rounded-lg flex items-center justify-center transition-colors"
                            >
                                <Github className="w-5 h-5 text-white/60 hover:text-white transition-colors" />
                            </a>
                            <a
                                href="/docs"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="w-10 h-10 bg-white/5 hover:bg-white/10 rounded-lg flex items-center justify-center transition-colors"
                            >
                                <BookOpen className="w-5 h-5 text-white/60 hover:text-white transition-colors" />
                            </a>
                        </div>
                    </div>

                    {/* Features Section */}
                    <div>
                        <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-purple-400" />
                            Features
                        </h4>
                        <ul className="space-y-3 text-white/70 text-sm">
                            <li>
                                <Link href="/capture" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full"></span>
                                    Quick Capture
                                </Link>
                            </li>
                            <li>
                                <Link href="/graph" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full"></span>
                                    Knowledge Graph
                                </Link>
                            </li>
                            <li>
                                <Link href="/search" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full"></span>
                                    Smart Search
                                </Link>
                            </li>
                            <li>
                                <Link href="/connections" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full"></span>
                                    Link Discovery
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Resources Section */}
                    <div>
                        <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Database className="w-4 h-4 text-cyan-400" />
                            Resources
                        </h4>
                        <ul className="space-y-3 text-white/70 text-sm">
                            <li>
                                <a href="/docs" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full"></span>
                                    Documentation
                                </a>
                            </li>
                            <li>
                                <a href="/api" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full"></span>
                                    API Reference
                                </a>
                            </li>
                            <li>
                                <a href="/guides" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full"></span>
                                    User Guides
                                </a>
                            </li>
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full"></span>
                                    GitHub
                                </a>
                            </li>
                        </ul>
                    </div>

                    {/* Get Started Section */}
                    <div>
                        <h4 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <Zap className="w-4 h-4 text-amber-400" />
                            Get Started
                        </h4>
                        <ul className="space-y-3 text-white/70 text-sm">
                            <li>
                                <Link href="/auth/signup" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full"></span>
                                    Create Account
                                </Link>
                            </li>
                            <li>
                                <Link href="/auth/login" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full"></span>
                                    Sign In
                                </Link>
                            </li>
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database/discussions" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full"></span>
                                    Community
                                </a>
                            </li>
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database/issues" className="hover:text-white transition-colors flex items-center gap-2">
                                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full"></span>
                                    Support
                                </a>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* Bottom Bar */}
                <div className="border-t border-white/10 mt-12 pt-8">
                    <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-white/60 text-sm">
                        <p>
                            &copy; {currentYear} MemEx - Part of Second Brain Database. Open source under MIT License.
                        </p>
                        <div className="flex gap-6">
                            <a href="/privacy" className="hover:text-white transition-colors">Privacy</a>
                            <a href="/terms" className="hover:text-white transition-colors">Terms</a>
                            <a href="https://github.com/rohanbatrain/second_brain_database/blob/main/CONTRIBUTING.md" className="hover:text-white transition-colors">Contributing</a>
                        </div>
                    </div>
                </div>
            </div>
        </footer>
    );
}
