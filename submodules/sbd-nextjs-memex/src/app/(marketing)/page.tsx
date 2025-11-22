"use client";

import { motion } from "framer-motion";
import { Brain, BookOpen, Zap, TrendingUp, ArrowRight, Github, Users, Target, Award, Clock } from "lucide-react";
import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import Stats from "@/components/Stats";
import HowItWorks from "@/components/HowItWorks";
import Testimonials from "@/components/Testimonials";
import FAQ from "@/components/FAQ";

export default function LandingPage() {
    return (
        <>
            <Header
                appName="MemEx"
                appIcon={<Brain className="w-8 h-8 text-indigo-400" />}
                primaryColor="indigo"
            />
            <div className="relative min-h-screen w-full h-full flex flex-col items-center overflow-hidden bg-[#040508] pt-16">
                <div className="w-full">
                    {/* Hero Section */}
                    <section className="relative pt-32 pb-16 container mx-auto px-4 z-10">
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.5 }}
                            className="text-center space-y-6 flex flex-col gap-8 items-center justify-center"
                        >
                            <motion.div
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: 0.2 }}
                                className="inline-block"
                            >
                                <span className="relative px-4 py-2 rounded-xl flex flex-row gap-2 items-center bg-white/10 text-sm text-white/90 backdrop-blur-sm border border-white/10 overflow-hidden">
                                    <motion.div
                                        className="absolute top-0 w-[10px] h-full bg-indigo-300 opacity-60 blur-md shadow-2xl"
                                        initial={{ left: "-10%" }}
                                        animate={{ left: "110%" }}
                                        transition={{
                                            repeat: Infinity,
                                            duration: 2,
                                            ease: "linear",
                                        }}
                                    />
                                    <Brain className="w-4 h-4 relative z-10" />
                                    <p className="relative z-10">
                                        SPACED REPETITION LEARNING SYSTEM
                                    </p>
                                </span>
                            </motion.div>

                            <motion.h1
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.4 }}
                                className="text-6xl md:text-7xl lg:text-8xl text-center bg-clip-text text-transparent bg-gradient-to-r from-white to-white/50 drop-shadow-[0_0_15px_rgba(255,255,255,0.3)] font-bold tracking-tight"
                            >
                                Master Anything with <br className="hidden md:block" /> MemEx
                            </motion.h1>

                            <motion.p
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.6 }}
                                className="max-w-3xl mx-auto text-lg text-white/80 leading-relaxed"
                            >
                                Leverage the power of spaced repetition to learn faster and remember longer.
                                Built on the proven SuperMemo-2 algorithm for optimal knowledge retention.
                            </motion.p>

                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.8 }}
                                className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto w-full"
                            >
                                <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10 hover:bg-white/10 transition-colors duration-300">
                                    <BookOpen className="w-8 h-8 text-indigo-400 shrink-0" />
                                    <div className="text-left">
                                        <p className="text-white font-medium">Smart Flashcards</p>
                                        <p className="text-white/60 text-sm">Create and organize decks efficiently</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10 hover:bg-white/10 transition-colors duration-300">
                                    <Zap className="w-8 h-8 text-purple-400 shrink-0" />
                                    <div className="text-left">
                                        <p className="text-white font-medium">SuperMemo-2</p>
                                        <p className="text-white/60 text-sm">Optimal review intervals</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10 hover:bg-white/10 transition-colors duration-300">
                                    <TrendingUp className="w-8 h-8 text-pink-400 shrink-0" />
                                    <div className="text-left">
                                        <p className="text-white font-medium">Track Progress</p>
                                        <p className="text-white/60 text-sm">Monitor your learning journey</p>
                                    </div>
                                </div>
                            </motion.div>

                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 1.0 }}
                                className="space-y-4 flex flex-col items-center justify-center pt-4"
                            >
                                <div className="flex flex-col sm:flex-row gap-4">
                                    <Link href="/auth/signup">
                                        <button className="bg-gradient-to-b from-indigo-600 to-indigo-800 px-8 py-3 rounded-lg text-white font-medium flex items-center justify-center gap-2 w-full sm:w-auto hover:from-indigo-700 hover:to-indigo-900 transition-all duration-300 border border-indigo-500/50">
                                            Start Learning
                                            <ArrowRight className="w-5 h-5" />
                                        </button>
                                    </Link>
                                    <Link href="/decks">
                                        <button className="bg-gradient-to-b from-gray-700 to-gray-900 px-8 py-3 rounded-lg text-white font-medium flex items-center justify-center gap-2 w-full sm:w-auto hover:from-gray-600 hover:to-gray-800 transition-all duration-300 border border-gray-600/50">
                                            <BookOpen className="w-5 h-5" />
                                            View Demo
                                        </button>
                                    </Link>
                                </div>
                                <p className="text-sm text-white/40">
                                    Don&apos;t have an account?{' '}
                                    <Link href="/auth/signup" className="text-indigo-400 hover:text-indigo-300 transition-colors">
                                        Get started
                                    </Link>
                                </p>
                                <p className="text-sm text-white/40 font-mono">
                                    Science-backed • Open source • Free forever
                                </p>
                            </motion.div>
                        </motion.div>
                    </section>

                    {/* Stats Section */}
                    <Stats
                        stats={[
                            {
                                icon: <Users className="w-8 h-8 text-indigo-400" />,
                                value: "10K+",
                                label: "Active Learners",
                                color: "bg-indigo-500/20"
                            },
                            {
                                icon: <BookOpen className="w-8 h-8 text-purple-400" />,
                                value: "1M+",
                                label: "Cards Reviewed",
                                color: "bg-purple-500/20"
                            },
                            {
                                icon: <Target className="w-8 h-8 text-pink-400" />,
                                value: "95%",
                                label: "Retention Rate",
                                color: "bg-pink-500/20"
                            },
                            {
                                icon: <Clock className="w-8 h-8 text-cyan-400" />,
                                value: "50%",
                                label: "Time Saved",
                                color: "bg-cyan-500/20"
                            }
                        ]}
                    />

                    {/* Features Section */}
                    <section className="min-h-screen w-full flex flex-col bg-gradient-to-b from-[#040508] to-[#0C0F15] justify-center items-center relative py-20">
                        <div className="container mx-auto px-4">
                            <div className="text-center mb-16">
                                <motion.h2
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true }}
                                    className="text-5xl md:text-6xl font-light mb-6 text-white"
                                >
                                    Why MemEx?
                                </motion.h2>
                                <motion.p
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true }}
                                    transition={{ delay: 0.1 }}
                                    className="text-xl text-white/70 max-w-3xl mx-auto"
                                >
                                    Science-backed learning techniques for maximum retention
                                </motion.p>
                            </div>

                            <motion.div
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.5 }}
                                viewport={{ once: true }}
                                className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-6xl mx-auto"
                            >
                                <FeatureCard
                                    icon={<Brain className="w-6 h-6 text-indigo-400" />}
                                    iconBg="bg-indigo-500/20"
                                    title="Intelligent Scheduling"
                                    description="Our SuperMemo-2 algorithm calculates the perfect time to review each card, maximizing retention while minimizing study time."
                                    list={[
                                        "Adaptive difficulty adjustment",
                                        "Personalized review intervals",
                                        "Forgetting curve optimization",
                                        "Automatic ease factor tuning"
                                    ]}
                                />
                                <FeatureCard
                                    icon={<BookOpen className="w-6 h-6 text-purple-400" />}
                                    iconBg="bg-purple-500/20"
                                    title="Flexible Deck Management"
                                    description="Organize your knowledge into decks and cards. Create, edit, and manage your learning materials with ease."
                                    list={[
                                        "Unlimited decks and cards",
                                        "Rich text formatting",
                                        "Import/export capabilities",
                                        "Tag and categorize content"
                                    ]}
                                    delay={0.1}
                                />
                                <FeatureCard
                                    icon={<Zap className="w-6 h-6 text-pink-400" />}
                                    iconBg="bg-pink-500/20"
                                    title="Efficient Learning"
                                    description="Study smarter, not harder. Focus on what you need to review and skip what you already know."
                                    list={[
                                        "Due card prioritization",
                                        "Session-based studying",
                                        "Quick review mode",
                                        "Mobile-friendly interface"
                                    ]}
                                    delay={0.2}
                                />
                                <FeatureCard
                                    icon={<TrendingUp className="w-6 h-6 text-cyan-400" />}
                                    iconBg="bg-cyan-500/20"
                                    title="Progress Tracking"
                                    description="Monitor your learning journey with detailed statistics and insights into your retention rates."
                                    list={[
                                        "Retention rate analytics",
                                        "Study streak tracking",
                                        "Performance graphs",
                                        "Learning milestones"
                                    ]}
                                    delay={0.3}
                                />
                            </motion.div>
                        </div>
                    </section>

                    {/* How It Works Section */}
                    <HowItWorks
                        title="How MemEx Works"
                        subtitle="Master any subject with our proven 4-step learning system"
                        steps={[
                            {
                                number: "01",
                                title: "Create Cards",
                                description: "Build your deck with questions and answers on any topic you want to master.",
                                icon: <BookOpen className="w-8 h-8 text-indigo-400" />
                            },
                            {
                                number: "02",
                                title: "Study Daily",
                                description: "Review cards based on the SuperMemo-2 algorithm's optimal scheduling.",
                                icon: <Brain className="w-8 h-8 text-purple-400" />
                            },
                            {
                                number: "03",
                                title: "Track Progress",
                                description: "Monitor your retention rates and identify areas that need more focus.",
                                icon: <TrendingUp className="w-8 h-8 text-pink-400" />
                            },
                            {
                                number: "04",
                                title: "Achieve Mastery",
                                description: "Reach long-term retention and truly master your chosen subjects.",
                                icon: <Award className="w-8 h-8 text-cyan-400" />
                            }
                        ]}
                    />

                    {/* Testimonials Section */}
                    <Testimonials
                        testimonials={[
                            {
                                quote: "MemEx transformed how I study for medical school. The spaced repetition algorithm ensures I never forget what I've learned, and I've cut my study time in half while improving my grades.",
                                author: "Sarah Chen",
                                role: "Medical Student, Johns Hopkins",
                                avatar: <div className="w-12 h-12 bg-indigo-500/20 rounded-full flex items-center justify-center"><Users className="w-6 h-6 text-indigo-400" /></div>
                            },
                            {
                                quote: "As a language learner, MemEx has been invaluable. I've mastered over 3,000 vocabulary words in 6 months, and the retention rate is incredible. The SuperMemo-2 algorithm really works!",
                                author: "Marcus Rodriguez",
                                role: "Language Enthusiast",
                                avatar: <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center"><Brain className="w-6 h-6 text-purple-400" /></div>
                            }
                        ]}
                    />

                    {/* FAQ Section */}
                    <FAQ
                        faqs={[
                            {
                                question: "What is spaced repetition and how does it work?",
                                answer: "Spaced repetition is a learning technique that involves reviewing information at increasing intervals. MemEx uses the SuperMemo-2 algorithm to calculate the optimal time to review each card based on how well you remember it, maximizing long-term retention while minimizing study time."
                            },
                            {
                                question: "Is MemEx free to use?",
                                answer: "Yes! MemEx is completely free and open source. You can create unlimited decks and cards, and there are no premium features locked behind a paywall. We believe effective learning tools should be accessible to everyone."
                            },
                            {
                                question: "Can I import my existing Anki decks?",
                                answer: "Yes, MemEx supports importing decks from Anki and other popular flashcard applications. We also support exporting your decks so you're never locked into our platform."
                            },
                            {
                                question: "How is MemEx different from Anki?",
                                answer: "While both use spaced repetition, MemEx offers a more modern, intuitive interface with real-time sync, better mobile support, and advanced analytics. We're also fully open source and actively maintained."
                            },
                            {
                                question: "Does MemEx work offline?",
                                answer: "Yes! MemEx has full offline support. You can study your cards without an internet connection, and your progress will sync automatically when you're back online."
                            },
                            {
                                question: "Can I share my decks with others?",
                                answer: "Absolutely! You can export your decks and share them with friends, classmates, or the community. We're also building a public deck library where users can discover and download decks created by others."
                            }
                        ]}
                    />

                    {/* CTA Section */}
                    <section className="min-h-screen w-full flex flex-col bg-gradient-to-b from-[#0C0F15] to-[#040508] justify-center items-center relative py-20">
                        <div className="container mx-auto px-4 text-center">
                            <h2 className="text-6xl md:text-7xl font-light mb-6 text-white">
                                Ready to Transform Your Learning?
                            </h2>
                            <p className="text-xl text-white/70 max-w-3xl mx-auto mb-12">
                                Join thousands of learners using MemEx to master new skills and retain knowledge effectively.
                            </p>

                            <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
                                <Link href="/auth/signup">
                                    <button className="bg-gradient-to-b from-indigo-600 to-indigo-800 px-8 py-4 rounded-lg text-white font-medium text-lg flex items-center gap-2 hover:from-indigo-700 hover:to-indigo-900 transition-all duration-300 border border-indigo-500/50">
                                        <Brain className="w-5 h-5" />
                                        Start Learning Free
                                    </button>
                                </Link>
                                <Link href="https://github.com/rohanbatrain/second_brain_database" target="_blank" rel="noopener noreferrer">
                                    <button className="bg-gradient-to-b from-gray-700 to-gray-900 px-8 py-4 rounded-lg text-white font-medium text-lg flex items-center gap-2 hover:from-gray-600 hover:to-gray-800 transition-all duration-300 border border-gray-600/50">
                                        <Github className="w-5 h-5" />
                                        View on GitHub
                                    </button>
                                </Link>
                            </div>

                            <div className="mt-12 text-center">
                                <p className="text-white/60 mb-4">Trusted by learners worldwide</p>
                                <div className="flex justify-center gap-8 text-white/40 text-sm">
                                    <span>Open Source</span>
                                    <span>•</span>
                                    <span>Privacy Focused</span>
                                    <span>•</span>
                                    <span>Science Backed</span>
                                </div>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
            <Footer
                appName="MemEx"
                appDescription="Master anything with spaced repetition. Built on the proven SuperMemo-2 algorithm for optimal knowledge retention."
                features={[
                    { name: "Smart Flashcards", href: "#" },
                    { name: "SuperMemo-2 Algorithm", href: "#" },
                    { name: "Progress Tracking", href: "#" },
                    { name: "Study Analytics", href: "#" }
                ]}
            />
        </>
    );
}

function FeatureCard({ icon, iconBg, title, description, list, delay = 0 }: {
    icon: React.ReactNode,
    iconBg: string,
    title: string,
    description: string,
    list: string[],
    delay?: number
}) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay }}
            viewport={{ once: true }}
            className="bg-white/5 backdrop-blur-sm rounded-lg p-8 border border-white/10 hover:bg-white/10 transition-colors duration-300"
        >
            <div className="flex items-center gap-4 mb-6">
                <div className={`w-12 h-12 ${iconBg} rounded-lg flex items-center justify-center`}>
                    {icon}
                </div>
                <h3 className="text-2xl font-semibold text-white">{title}</h3>
            </div>
            <p className="text-white/80 mb-4">
                {description}
            </p>
            <ul className="text-white/70 space-y-2">
                {list.map((item, i) => (
                    <li key={i}>• {item}</li>
                ))}
            </ul>
        </motion.div>
    );
}
