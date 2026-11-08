import { Text } from 'react-native';

import { colors } from '@/components/theme';
import { Centered } from '@/components/ui';

export default function BudgetsScreen() {
  return (
    <Centered>
      <Text style={{ color: colors.muted }}>Budżety pojawią się w tygodniu 4.</Text>
    </Centered>
  );
}
