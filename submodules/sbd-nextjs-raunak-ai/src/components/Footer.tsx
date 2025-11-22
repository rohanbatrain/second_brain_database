"use client";

import { Github, BookOpen } from "lucide-react";
import Link from "next/link";

interface FooterProps {
    appName: string;
    appDescription: string;
    features?: Array<{ name: string; href: string }>;
}

export default function Footer({ appName, appDescription, features = [] }: FooterProps) {
    const currentYear = new Date().getFullYear();

    return (
        <footer className="w-full bg-black/50 backdrop-blur-sm border-t border-white/10 py-12">
            <div className="container mx-auto px-4">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                    {/* Brand Section */}
                    <div>
                        <h3 className="text-2xl font-bold text-white mb-4">{appName}</h3>
                        <p className="text-white/70 mb-4 text-sm">
                            {appDescription}
                        </p>
                        <div className="flex gap-4">
                            <a href="https://github.com/rohanbatrain/second_brain_database" target="_blank" rel="noopener noreferrer">
                                <Github className="w-6 h-6 text-white/60 hover:text-white cursor-pointer transition-colors" />
                            </a>
                            <a href="/docs" target="_blank" rel="noopener noreferrer">
                                <BookOpen className="w-6 h-6 text-white/60 hover:text-white cursor-pointer transition-colors" />
                            </a>
                        </div>
                    </div>

                    {/* Features Section */}
                    {features.length > 0 && (
                        <div>
                            <h4 className="text-lg font-semibold text-white mb-4">Features</h4>
                            <ul className="space-y-2 text-white/70 text-sm">
                                {features.map((feature) => (
                                    <li key={feature.href}>
                                        <a href={feature.href} className="hover:text-white transition-colors">
                                            {feature.name}
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Resources Section */}
                    <div>
                        <h4 className="text-lg font-semibold text-white mb-4">Resources</h4>
                        <ul className="space-y-2 text-white/70 text-sm">
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database" className="hover:text-white transition-colors">
                                    GitHub Repository
                                </a>
                            </li>
                            <li>
                                <a href="/docs" className="hover:text-white transition-colors">
                                    Documentation
                                </a>
                            </li>
                            <li>
                                <Link href="/auth/signup" className="hover:text-white transition-colors">
                                    Get Started
                                </Link>
                            </li>
                            <li>
                                <Link href="/auth/login" className="hover:text-white transition-colors">
                                    Sign In
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Community Section */}
                    <div>
                        <h4 className="text-lg font-semibold text-white mb-4">Community</h4>
                        <ul className="space-y-2 text-white/70 text-sm">
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database/discussions" className="hover:text-white transition-colors">
                                    Discussions
                                </a>
                            </li>
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database/issues" className="hover:text-white transition-colors">
                                    Issue Tracker
                                </a>
                            </li>
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database/blob/main/CONTRIBUTING.md" className="hover:text-white transition-colors">
                                    Contributing
                                </a>
                            </li>
                            <li>
                                <a href="https://github.com/rohanbatrain/second_brain_database" className="hover:text-white transition-colors">
                                    Roadmap
                                </a>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* Copyright */}
                <div className="border-t border-white/10 mt-8 pt-8 text-center text-white/60 text-sm">
                    <p>
                        &copy; {currentYear} Second Brain Database. Open source under MIT License.
                    </p>
                </div>
            </div>
        </footer>
    );
}
