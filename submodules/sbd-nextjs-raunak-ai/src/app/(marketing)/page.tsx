"use client";

import { motion } from "framer-motion";
import { Brain, Sparkles, MessageSquare, Zap, ArrowRight, Github, Users, Target, TrendingUp, Star, Bot } from "lucide-react";
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
                appName="Raunak AI"
                appIcon={<Brain className="w-8 h-8 text-violet-400" />}
                primaryColor="violet"
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
                                        className="absolute top-0 w-[10px] h-full bg-violet-300 opacity-60 blur-md shadow-2xl"
                                        initial={{ left: "-10%" }}
                                        animate={{ left: "110%" }}
                                        transition={{
                                            repeat: Infinity,
                                            duration: 2,
                                            ease: "linear",
                                        }}
                                    />
                                    <Sparkles className="w-4 h-4 relative z-10" />
                                    <p className="relative z-10">
                                        AI-POWERED ASSISTANT PLATFORM
                                    </p>
                                </span>
                            </motion.div>

                            <motion.h1
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.4 }}
                                className="text-6xl md:text-7xl lg:text-8xl text-center bg-clip-text text-transparent bg-gradient-to-r from-white to-white/50 drop-shadow-[0_0_15px_rgba(255,255,255,0.3)] font-bold tracking-tight"
                            >
                                Your AI <br className="hidden md:block" /> Assistant
                            </motion.h1>

                            <motion.p
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.6 }}
                                className="max-w-3xl mx-auto text-lg text-white/80 leading-relaxed"
                            >
                                Intelligent AI assistant powered by RAG, MCP tools, and advanced document processing.
                                Get instant answers, automate tasks, and unlock the power of your knowledge base.
                            </motion.p>

                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.8 }}
                                className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto w-full"
                            >
                                <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10 hover:bg-white/10 transition-colors duration-300">
                                    <Bot className="w-8 h-8 text-violet-400 shrink-0" />
                                    <div className="text-left">
                                        <p className="text-white font-medium">Smart Chat</p>
                                        <p className="text-white/60 text-sm">Natural conversations with AI</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10 hover:bg-white/10 transition-colors duration-300">
                                    <Brain className="w-8 h-8 text-pink-400 shrink-0" />
                                    <div className="text-left">
                                        <p className="text-white font-medium">RAG Search</p>
                                        <p className="text-white/60 text-sm">Query your documents</p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 bg-white/5 backdrop-blur-sm rounded-lg p-4 border border-white/10 hover:bg-white/10 transition-colors duration-300">
                                    <Zap className="w-8 h-8 text-amber-400 shrink-0" />
                                    <div className="text-left">
                                        <p className="text-white font-medium">MCP Tools</p>
                                        <p className="text-white/60 text-sm">138+ integrated tools</p>
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
                                        <button className="bg-gradient-to-b from-violet-600 to-violet-800 px-8 py-3 rounded-lg text-white font-medium flex items-center justify-center gap-2 w-full sm:w-auto hover:from-violet-700 hover:to-violet-900 transition-all duration-300 border border-violet-500/50">
                                            Start Chatting
                                            <ArrowRight className="w-5 h-5" />
                                        </button>
                                    </Link>
                                    <Link href="/dashboard">
                                        <button className="bg-gradient-to-b from-gray-700 to-gray-900 px-8 py-3 rounded-lg text-white font-medium flex items-center justify-center gap-2 w-full sm:w-auto hover:from-gray-600 hover:to-gray-800 transition-all duration-300 border border-gray-600/50">
                                            <Bot className="w-5 h-5" />
                                            Try Demo
                                        </button>
                                    </Link>
                                </div>
                                <p className="text-sm text-white/40">
                                    Don&apos;t have an account?{' '}
                                    <Link href="/auth/signup" className="text-violet-400 hover:text-violet-300 transition-colors">
                                        Sign up free
                                    </Link>
                                </p>
                                <p className="text-sm text-white/40 font-mono">
                                    Intelligent • Powerful • Context-Aware
                                </p>
                            </motion.div>
                        </motion.div>
                    </section>

                    {/* Stats Section */}
                    <Stats
                        stats={[
                            {
                                icon: <Users className="w-8 h-8 text-violet-400" />,
                                value: "50K+",
                                label: "Active Users",
                                color: "bg-violet-500/20"
                            },
                            {
                                icon: <MessageSquare className="w-8 h-8 text-blue-400" />,
                                value: "1M+",
                                label: "Conversations",
                                color: "bg-blue-500/20"
                            },
                            {
                                icon: <Target className="w-8 h-8 text-green-400" />,
                                value: "95%",
                                label: "Accuracy Rate",
                                color: "bg-green-500/20"
                            },
                            {
                                icon: <Zap className="w-8 h-8 text-amber-400" />,
                                value: "<2s",
                                label: "Response Time",
                                color: "bg-amber-500/20"
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
                                    AI Capabilities
                                </motion.h2>
                                <motion.p
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    viewport={{ once: true }}
                                    transition={{ delay: 0.1 }}
                                    className="text-xl text-white/70 max-w-3xl mx-auto"
                                >
                                    Advanced AI features to supercharge your productivity
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
                                    icon={<Bot className="w-6 h-6 text-violet-400" />}
                                    iconBg="bg-violet-500/20"
                                    title="Conversational AI"
                                    description="Engage in natural conversations with an AI that understands context, remembers history, and provides intelligent responses."
                                    list={[
                                        "Natural language understanding",
                                        "Context-aware responses",
                                        "Conversation history",
                                        "Multi-turn dialogues"
                                    ]}
                                />
                                <FeatureCard
                                    icon={<Brain className="w-6 h-6 text-pink-400" />}
                                    iconBg="bg-pink-500/20"
                                    title="RAG Search"
                                    description="Query your documents with semantic search powered by vector embeddings and retrieval-augmented generation."
                                    list={[
                                        "Semantic document search",
                                        "Vector embeddings",
                                        "Citation tracking",
                                        "Multi-document queries"
                                    ]}
                                    delay={0.1}
                                />
                                <FeatureCard
                                    icon={<Zap className="w-6 h-6 text-amber-400" />}
                                    iconBg="bg-amber-500/20"
                                    title="MCP Integration"
                                    description="Access 138+ tools across family management, authentication, shop operations, and more through the MCP protocol."
                                    list={[
                                        "Family management tools",
                                        "Authentication & security",
                                        "Shop operations",
                                        "Admin & monitoring"
                                    ]}
                                    delay={0.2}
                                />
                                <FeatureCard
                                    icon={<Sparkles className="w-6 h-6 text-cyan-400" />}
                                    iconBg="bg-cyan-500/20"
                                    title="Document Processing"
                                    description="Advanced document intelligence with OCR, table extraction, and AI-powered analysis of PDFs, DOCX, and more."
                                    list={[
                                        "OCR text extraction",
                                        "Table recognition",
                                        "Figure detection",
                                        "Multi-format support"
                                    ]}
                                    delay={0.3}
                                />
                            </motion.div>
                        </div>
                    </section>

                    {/* How It Works Section */}
                    <HowItWorks
                        title="How Raunak AI Works"
                        subtitle="Intelligent assistance powered by RAG and MCP in 4 steps"
                        steps={[
                            {
                                number: "01",
                                title: "Ask Questions",
                                description: "Chat naturally with Raunak AI about your documents, tasks, or any topic you need help with.",
                                icon: <MessageSquare className="w-8 h-8 text-violet-400" />
                            },
                            {
                                number: "02",
                                title: "RAG Processing",
                                description: "AI retrieves relevant context from your documents using advanced RAG technology.",
                                icon: <Brain className="w-8 h-8 text-blue-400" />
                            },
                            {
                                number: "03",
                                title: "Tool Execution",
                                description: "Access 138+ tools via MCP for family management, shop operations, and more.",
                                icon: <Zap className="w-8 h-8 text-amber-400" />
                            },
                            {
                                number: "04",
                                title: "Get Answers",
                                description: "Receive accurate, contextual responses with citations and actionable insights.",
                                icon: <Sparkles className="w-8 h-8 text-green-400" />
                            }
                        ]}
                    />

                    {/* Testimonials Section */}
                    <Testimonials
                        testimonials={[
                            {
                                quote: "Raunak AI transformed how I interact with my knowledge base. The RAG-powered search finds exactly what I need instantly, and the MCP tools let me manage everything from one interface. It's like having a personal assistant that knows everything.",
                                author: "Priya Sharma",
                                role: "Knowledge Worker & Researcher",
                                avatar: <div className="w-12 h-12 bg-violet-500/20 rounded-full flex items-center justify-center"><Brain className="w-6 h-6 text-violet-400" /></div>
                            },
                            {
                                quote: "The document intelligence is incredible. I can ask questions about hundreds of PDFs and get accurate answers with citations in seconds. The sub-2-second response time makes it feel like a natural conversation.",
                                author: "Alex Thompson",
                                role: "Software Engineer",
                                avatar: <div className="w-12 h-12 bg-blue-500/20 rounded-full flex items-center justify-center"><Sparkles className="w-6 h-6 text-blue-400" /></div>
                            }
                        ]}
                    />

                    {/* FAQ Section */}
                    <FAQ
                        faqs={[
                            {
                                question: "What is RAG and how does it work?",
                                answer: "RAG (Retrieval-Augmented Generation) is an AI technique that retrieves relevant information from your documents before generating responses. This ensures answers are grounded in your actual data, not just the AI's training. Raunak AI uses advanced RAG with Qdrant vector database for lightning-fast, accurate retrieval."
                            },
                            {
                                question: "What is MCP and what tools are available?",
                                answer: "MCP (Model Context Protocol) allows AI to access external tools and services. Raunak AI includes 138+ tools across family management, authentication, shop operations, document processing, and more. You can ask the AI to perform actions like managing family members, processing documents, or checking shop inventory."
                            },
                            {
                                question: "How secure is my data?",
                                answer: "All your documents and conversations are encrypted and stored securely. RAG processing happens locally on your infrastructure, and we never train models on your data. You maintain full control and ownership of your information."
                            },
                            {
                                question: "Can I use my own documents?",
                                answer: "Absolutely! Upload PDFs, Word documents, text files, and more. Raunak AI uses Docling OCR to extract text from any document format, then indexes it for instant retrieval. You can query across all your documents simultaneously."
                            },
                            {
                                question: "What LLM models does Raunak AI support?",
                                answer: "Raunak AI works with Ollama, supporting models like Llama 3, Mistral, and others. You can run models locally for complete privacy or use cloud providers. The RAG system works with any LLM that supports the Ollama API."
                            },
                            {
                                question: "How fast are the responses?",
                                answer: "Average response time is under 2 seconds, including RAG retrieval and LLM generation. The Qdrant vector database provides sub-millisecond similarity search, and we use streaming responses so you see answers as they're generated."
                            }
                        ]}
                    />

                    {/* CTA Section */}
                    <section className="min-h-screen w-full flex flex-col bg-gradient-to-b from-[#0C0F15] to-[#040508] justify-center items-center relative py-20">
                        <div className="container mx-auto px-4 text-center">
                            <h2 className="text-6xl md:text-7xl font-light mb-6 text-white">
                                Ready to Unlock AI Power?
                            </h2>
                            <p className="text-xl text-white/70 max-w-3xl mx-auto mb-12">
                                Join users worldwide leveraging AI to automate tasks, find answers, and boost productivity.
                            </p>

                            <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
                                <Link href="/auth/signup">
                                    <button className="bg-gradient-to-b from-violet-600 to-violet-800 px-8 py-4 rounded-lg text-white font-medium text-lg flex items-center gap-2 hover:from-violet-700 hover:to-violet-900 transition-all duration-300 border border-violet-500/50">
                                        <Sparkles className="w-5 h-5" />
                                        Get Started Free
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
                                <p className="text-white/60 mb-4">Trusted by AI enthusiasts worldwide</p>
                                <div className="flex justify-center gap-8 text-white/40 text-sm">
                                    <span>Intelligent</span>
                                    <span>•</span>
                                    <span>Powerful</span>
                                    <span>•</span>
                                    <span>Context-Aware</span>
                                </div>
                            </div>
                        </div>
                    </section>
                </div>
                <Footer
                    appName="Raunak AI"
                    appDescription="AI-powered knowledge management with RAG, MCP tools, and local LLM chat for intelligent document processing and task automation."
                    features={[
                        { name: "RAG Chat", href: "#" },
                        { name: "Document Intelligence", href: "#" },
                        { name: "MCP Tools", href: "#" },
                        { name: "LLM Integration", href: "#" }
                    ]}
                />
            </div >
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
