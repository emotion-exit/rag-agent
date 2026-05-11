import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin']
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin']
});

export const metadata: Metadata = {
  title: {
    template: '%s - RAG Agent',
    default: 'RAG Agent'
  },
  description: 'create by next'
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className='h-screen w-screen overflow-y-hidden px-[25%] py-20 flex flex-col items-center'>
        {children}
      </body>
    </html>
  );
}
