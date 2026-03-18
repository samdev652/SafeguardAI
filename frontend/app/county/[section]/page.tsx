import { notFound } from 'next/navigation';
import CountyPortalPage, { CountyTab } from '@/components/CountyPortalPage';

const validSections: CountyTab[] = [
  'overview',
  'active-threats',
  'alert-history',
  'registered-users',
  'incident-reports',
  'dispatch-log',
  'settings',
];

export default function CountySectionPage({ params }: { params: { section: string } }) {
  const section = params.section as CountyTab;
  if (!validSections.includes(section)) {
    notFound();
  }

  return <CountyPortalPage section={section} />;
}
