"use client";

import { motion } from "framer-motion";

interface Step {
    number: string;
    title: string;
    description: string;
    icon: React.ReactNode;
}

interface HowItWorksProps {
    title: string;
    subtitle: string;
    steps: Step[];
}

export default function HowItWorks({ title, subtitle, steps }: HowItWorksProps) {
    return (
        <section className="min-h-screen w-full flex flex-col bg-gradient-to-b from-[#0C0F15] to-[#040508] justify-center items-center relative py-20">
            <div className="container mx-auto px-4">
                <div className="text-center mb-16">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-5xl md:text-6xl font-light mb-6 text-white"
                    >
                        {title}
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-xl text-white/70 max-w-3xl mx-auto"
                    >
                        {subtitle}
                    </motion.p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-6xl mx-auto">
                    {steps.map((step, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="relative"
                        >
                            <div className="bg-white/5 backdrop-blur-sm rounded-lg p-6 border border-white/10 hover:bg-white/10 transition-colors duration-300 h-full">
                                <div className="text-6xl font-bold text-white/10 mb-4">{step.number}</div>
                                <div className="mb-4">{step.icon}</div>
                                <h3 className="text-xl font-semibold text-white mb-3">{step.title}</h3>
                                <p className="text-white/70">{step.description}</p>
                            </div>
                            {index < steps.length - 1 && (
                                <div className="hidden lg:block absolute top-1/2 -right-4 w-8 h-0.5 bg-gradient-to-r from-white/20 to-transparent" />
                            )}
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
