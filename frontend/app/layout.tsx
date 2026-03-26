import type { Metadata } from 'next';
import './globals.css';
import Providers from '@/components/Providers';
import dynamic from 'next/dynamic';
const ChatWidget = dynamic(() => import('@/components/ChatWidget'), { ssr: false });

export const metadata: Metadata = {
  title: 'Safeguard AI',
  description: "Kenya's AI-powered multi-hazard early warning and anticipatory response platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Fetch threatCount from API or context if available, else pass 0
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
          <ChatWidget />
        </Providers>
      </body>
    </html>
  );
}
