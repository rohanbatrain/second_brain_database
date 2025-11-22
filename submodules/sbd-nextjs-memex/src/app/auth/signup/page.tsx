'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/lib/store/auth-store';
import { useServerStore } from '@/lib/store/server-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Eye, EyeOff, Lock, Mail, User, Brain, CheckCircle, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import type { AuthError } from '@/lib/types/api';

export default function SignupPage() {
    const router = useRouter();
    const { isConfigured } = useServerStore();
    const signup = useAuthStore((state) => state.signup);
    const error = useAuthStore((state) => state.error);
    const clearError = useAuthStore((state) => state.clearError);
    const [isLoading, setIsLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [signupSuccess, setSignupSuccess] = useState(false);
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        confirmPassword: '',
    });
    const [errors, setErrors] = useState<{ username?: string; email?: string; password?: string; confirmPassword?: string }>({});

    useEffect(() => {
        if (error) {
            clearError();
        }
    }, [formData.username, formData.email, formData.password, formData.confirmPassword, error, clearError]);

    const validateForm = () => {
        const newErrors: { username?: string; email?: string; password?: string; confirmPassword?: string } = {};

        if (!formData.username) {
            newErrors.username = 'Username is required';
        } else if (formData.username.length < 3) {
            newErrors.username = 'Username must be at least 3 characters';
        }

        if (!formData.email) {
            newErrors.email = 'Email is required';
        } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
            newErrors.email = 'Please enter a valid email address';
        }

        if (!formData.password) {
            newErrors.password = 'Password is required';
        } else if (formData.password.length < 8) {
            newErrors.password = 'Password must be at least 8 characters';
        }

        if (!formData.confirmPassword) {
            newErrors.confirmPassword = 'Please confirm your password';
        } else if (formData.password !== formData.confirmPassword) {
            newErrors.confirmPassword = 'Passwords do not match';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!validateForm()) {
            return;
        }

        setIsLoading(true);

        try {
            await signup({
                username: formData.username,
                email: formData.email,
                password: formData.password,
            });

            setSignupSuccess(true);
            toast.success('Account created successfully!');
        } catch (error) {
            console.error('Signup error:', error);
            setIsLoading(false);
        }
    };

    const getErrorDisplay = (authError: AuthError) => {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1">
                        <h4 className="text-sm font-medium text-red-800 mb-1">
                            {authError.error}
                        </h4>
                        <p className="text-sm text-red-700">
                            {authError.message}
                        </p>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900 flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full mb-4 shadow-lg shadow-green-500/20">
                        <Brain className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold text-white mb-2">Create Account</h1>
                    <p className="text-purple-200">Join MemEx</p>
                    <p className="text-sm text-purple-300/60 mt-1">Start your learning journey</p>
                </div>

                {!isConfigured && (
                    <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg backdrop-blur-sm">
                        <p className="text-sm text-yellow-200">
                            Server not configured.{' '}
                            <a href="/server-setup" className="font-medium text-yellow-100 underline hover:text-white">
                                Configure server
                            </a>
                        </p>
                    </div>
                )}

                <Card className="shadow-2xl border-white/10 bg-white/5 backdrop-blur-md">
                    <CardHeader className="space-y-1 pb-4">
                        <CardTitle className="text-xl font-semibold text-center text-white">Sign Up</CardTitle>
                        <CardDescription className="text-center text-purple-200/70">
                            Create your MemEx account
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {error && getErrorDisplay(error)}

                        {signupSuccess && (
                            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4 mb-4">
                                <div className="flex items-start gap-3">
                                    <CheckCircle className="w-5 h-5 text-green-400 mt-0.5 flex-shrink-0" />
                                    <div className="flex-1">
                                        <h4 className="text-sm font-medium text-green-300 mb-1">
                                            Account Created!
                                        </h4>
                                        <p className="text-sm text-green-200/80 mb-3">
                                            Please check your email to verify your account.
                                        </p>
                                        <Button
                                            onClick={() => router.push('/auth/login')}
                                            className="w-full bg-green-600 hover:bg-green-700 border-0"
                                        >
                                            Go to Login
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {!signupSuccess && (
                            <>
                                <form onSubmit={handleSubmit} className="space-y-6">
                                    <div className="space-y-2">
                                        <Label htmlFor="username" className="text-sm font-medium text-purple-100">
                                            Username
                                        </Label>
                                        <div className="relative">
                                            <User className="absolute left-3 top-3 h-4 w-4 text-purple-300" />
                                            <Input
                                                id="username"
                                                type="text"
                                                placeholder="Choose a username"
                                                value={formData.username}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, username: e.target.value })}
                                                disabled={isLoading}
                                                className={`pl-10 h-11 transition-all duration-200 bg-white/5 border-white/10 text-white placeholder:text-purple-300/50 ${errors.username ? 'border-red-400 focus:border-red-500' : 'focus:border-green-400'
                                                    }`}
                                            />
                                        </div>
                                        {errors.username && (
                                            <p className="text-sm text-red-400">{errors.username}</p>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="email" className="text-sm font-medium text-purple-100">
                                            Email Address
                                        </Label>
                                        <div className="relative">
                                            <Mail className="absolute left-3 top-3 h-4 w-4 text-purple-300" />
                                            <Input
                                                id="email"
                                                type="email"
                                                placeholder="Enter your email"
                                                value={formData.email}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, email: e.target.value })}
                                                disabled={isLoading}
                                                className={`pl-10 h-11 transition-all duration-200 bg-white/5 border-white/10 text-white placeholder:text-purple-300/50 ${errors.email ? 'border-red-400 focus:border-red-500' : 'focus:border-green-400'
                                                    }`}
                                            />
                                        </div>
                                        {errors.email && (
                                            <p className="text-sm text-red-400">{errors.email}</p>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="password" className="text-sm font-medium text-purple-100">
                                            Password
                                        </Label>
                                        <div className="relative">
                                            <Lock className="absolute left-3 top-3 h-4 w-4 text-purple-300" />
                                            <Input
                                                id="password"
                                                type={showPassword ? 'text' : 'password'}
                                                placeholder="Create a password"
                                                value={formData.password}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, password: e.target.value })}
                                                disabled={isLoading}
                                                className={`pl-10 pr-10 h-11 transition-all duration-200 bg-white/5 border-white/10 text-white placeholder:text-purple-300/50 ${errors.password ? 'border-red-400 focus:border-red-500' : 'focus:border-green-400'
                                                    }`}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-3 top-3 text-purple-300 hover:text-white transition-colors"
                                            >
                                                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </button>
                                        </div>
                                        {errors.password && (
                                            <p className="text-sm text-red-400">{errors.password}</p>
                                        )}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="confirmPassword" className="text-sm font-medium text-purple-100">
                                            Confirm Password
                                        </Label>
                                        <div className="relative">
                                            <CheckCircle className="absolute left-3 top-3 h-4 w-4 text-purple-300" />
                                            <Input
                                                id="confirmPassword"
                                                type={showConfirmPassword ? 'text' : 'password'}
                                                placeholder="Confirm your password"
                                                value={formData.confirmPassword}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                                disabled={isLoading}
                                                className={`pl-10 pr-10 h-11 transition-all duration-200 bg-white/5 border-white/10 text-white placeholder:text-purple-300/50 ${errors.confirmPassword ? 'border-red-400 focus:border-red-500' : 'focus:border-green-400'
                                                    }`}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                                className="absolute right-3 top-3 text-purple-300 hover:text-white transition-colors"
                                            >
                                                {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </button>
                                        </div>
                                        {errors.confirmPassword && (
                                            <p className="text-sm text-red-400">{errors.confirmPassword}</p>
                                        )}
                                    </div>

                                    <Button
                                        type="submit"
                                        className="w-full h-11 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-medium transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-green-500/25 border-0"
                                        disabled={isLoading}
                                    >
                                        {isLoading ? (
                                            <div className="flex items-center gap-2">
                                                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                                Creating account...
                                            </div>
                                        ) : (
                                            'Create Account'
                                        )}
                                    </Button>
                                </form>

                                <div className="mt-6 text-center">
                                    <p className="text-sm text-purple-200/70">
                                        Already have an account?{' '}
                                        <Link
                                            href="/auth/login"
                                            className="text-green-400 hover:text-green-300 font-medium transition-colors hover:underline"
                                        >
                                            Sign in here
                                        </Link>
                                    </p>
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
