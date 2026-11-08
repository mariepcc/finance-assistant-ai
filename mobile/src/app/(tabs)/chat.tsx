import { Text } from 'react-native';

import { colors } from '@/components/theme';
import { Centered } from '@/components/ui';

export default function ChatScreen() {
  return (
    <Centered>
      <Text style={{ color: colors.muted }}>Asystent pojawi się w tygodniu 3.</Text>
    </Centered>
  );
}
