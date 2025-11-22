"use client";

import { motion } from "framer-motion";
import { TrendingUp, Users, Star, Zap } from "lucide-react";

interface StatsProps {
    stats: Array<{
        icon: React.ReactNode;
        value: string;
        label: string;
        color: string;
    }>;
}

export default function Stats({ stats }: StatsProps) {
    return (
        <section className="w-full bg-gradient-to-b from-[#040508] to-[#0C0F15] py-20">
            <div className="container mx-auto px-4">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-6xl mx-auto"
                >
                    {stats.map((stat, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="text-center"
                        >
                            <div className={`w-16 h-16 ${stat.color} rounded-full flex items-center justify-center mx-auto mb-4`}>
                                {stat.icon}
                            </div>
                            <div className="text-4xl font-bold text-white mb-2">{stat.value}</div>
                            <div className="text-white/60">{stat.label}</div>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
