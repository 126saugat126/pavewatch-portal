import { Button } from '@mantine/core';
import { IconMapOff } from '@tabler/icons-react';
import { Link } from 'react-router-dom';
import { EmptyBlock } from '../components/States';

export default function NotFoundPage() {
  return (
    <EmptyBlock
      icon={<IconMapOff size={22} />}
      title="Page not found"
      action={
        <Button component={Link} to="/" variant="default" mt="xs">
          Go to companies
        </Button>
      }
    >
      The link may be outdated, or the survey may have been replaced by a newer upload.
    </EmptyBlock>
  );
}
