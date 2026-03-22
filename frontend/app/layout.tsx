import type { Metadata } from 'next';
import './globals.css';
import Providers from '@/components/Providers';
import ChatbotWidget from '@/components/ChatbotWidget';

export const metadata: Metadata = {
  title: 'Safeguard AI',
  description: "Kenya's AI-powered multi-hazard early warning and anticipatory response platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Fetch threatCount from API or context if available, else pass 0
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
        <ChatbotWidget threatCount={0} />
      </body>
    </html>
  );
}
