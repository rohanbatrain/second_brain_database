/**
 * Sidebar Navigation Component
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
    MessageSquare,
    FileText,
    Wrench,
    BarChart3,
    Settings,
    ChevronLeft,
    ChevronRight,
    Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

const navItems = [
    { icon: MessageSquare, label: 'Chat', href: '/' },
    { icon: FileText, label: 'Documents', href: '/documents' },
    { icon: Wrench, label: 'Tools', href: '/tools' },
    { icon: BarChart3, label: 'Analytics', href: '/analytics' },
    { icon: Settings, label: 'Settings', href: '/settings' },
];

export function Sidebar() {
    const [collapsed, setCollapsed] = useState(false);
    const pathname = usePathname();

    return (
        <motion.aside
            initial={false}
            animate={{ width: collapsed ? 80 : 240 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="glass relative flex flex-col h-screen border-r border-border/50"
        >
            {/* Logo */}
            <div className="flex items-center justify-between p-4 h-16">
                {!collapsed && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center gap-2"
                    >
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                            <Sparkles className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-bold text-lg gradient-text">Raunak AI</span>
                    </motion.div>
                )}
                {collapsed && (
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center mx-auto">
                        <Sparkles className="w-5 h-5 text-white" />
                    </div>
                )}
            </div>

            <Separator className="opacity-50" />

            {/* Navigation */}
            <nav className="flex-1 p-3 space-y-1">
                {navItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname === item.href;

                    return (
                        <Link key={item.href} href={item.href}>
                            <Button
                                variant={isActive ? 'secondary' : 'ghost'}
                                className={cn(
                                    'w-full justify-start gap-3 transition-all duration-200',
                                    collapsed && 'justify-center px-2',
                                    isActive && 'bg-primary/10 text-primary font-medium'
                                )}
                            >
                                <Icon className="w-5 h-5 flex-shrink-0" />
                                {!collapsed && <span>{item.label}</span>}
                            </Button>
                        </Link>
                    );
                })}
            </nav>

            {/* Collapse Toggle */}
            <div className="p-3">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCollapsed(!collapsed)}
                    className="w-full"
                >
                    {collapsed ? (
                        <ChevronRight className="w-4 h-4" />
                    ) : (
                        <>
                            <ChevronLeft className="w-4 h-4 mr-2" />
                            <span>Collapse</span>
                        </>
                    )}
                </Button>
            </div>
        </motion.aside>
    );
}
